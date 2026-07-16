#!/usr/bin/env python3
"""Real Renode and QEMU execution probes for Aurora Code WS12."""

from __future__ import annotations

import os
import shutil
import struct
from pathlib import Path
from typing import Any

from simulation_tooling import find_tool, run_command, run_until_marker, tail, unavailable


RENODE_MARKER = "0xA6120042"
RASPBERRY_MARKER = "AURORA_WS12_RASPBERRY_HEARTBEAT"
OS_MARKER = "AURORA_WS12_OS_HEARTBEAT"

NRF_SOURCE = r'''#![no_std]
#![no_main]

use core::panic::PanicInfo;
use core::ptr::write_volatile;

#[repr(C)]
struct VectorTable {
    initial_stack: u32,
    reset: unsafe extern "C" fn() -> !,
}

unsafe impl Sync for VectorTable {}

#[used]
#[link_section = ".vector_table"]
static VECTORS: VectorTable = VectorTable {
    initial_stack: 0x2004_0000,
    reset,
};

#[no_mangle]
unsafe extern "C" fn reset() -> ! {
    write_volatile(0x2000_0100 as *mut u32, 0xA612_0042);
    write_volatile(0x5000_0518 as *mut u32, 1 << 24);
    write_volatile(0x5000_050C as *mut u32, 1 << 24);
    loop { core::hint::spin_loop(); }
}

#[panic_handler]
fn panic(_: &PanicInfo) -> ! { loop { core::hint::spin_loop(); } }
'''

NRF_LINKER = r'''ENTRY(reset)
MEMORY {
  FLASH : ORIGIN = 0x00000000, LENGTH = 1M
  RAM   : ORIGIN = 0x20000000, LENGTH = 256K
}
SECTIONS {
  .vector_table : { KEEP(*(.vector_table)) } > FLASH
  .text : { *(.text .text.*) *(.rodata .rodata.*) } > FLASH
  .data : { *(.data .data.*) } > RAM AT > FLASH
  .bss (NOLOAD) : { *(.bss .bss.*) *(COMMON) } > RAM
  /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) }
}
'''

RASPBERRY_SOURCE = r'''#![no_std]
#![no_main]

use core::arch::global_asm;
use core::panic::PanicInfo;
use core::ptr::{read_volatile, write_volatile};

const UART_DR: *mut u32 = 0x3F20_1000 as *mut u32;
const UART_FR: *const u32 = 0x3F20_1018 as *const u32;
const UART_CR: *mut u32 = 0x3F20_1030 as *mut u32;

global_asm!(r#"
    .section .text._start, "ax"
    .global _start
_start:
    mrc p15, 0, r0, c0, c0, 5
    ands r0, r0, #3
    bne 2f
    ldr sp, =0x08000000
    bl rust_main
1:
    b 1b
2:
    wfe
    b 2b
"#);

#[no_mangle]
pub unsafe extern "C" fn rust_main() -> ! {
    write_volatile(UART_CR, (1 << 8) | 1);
    for byte in b"AURORA_WS12_RASPBERRY_HEARTBEAT\r\n" {
        while read_volatile(UART_FR) & (1 << 5) != 0 {}
        write_volatile(UART_DR, *byte as u32);
    }
    loop { core::hint::spin_loop(); }
}

#[panic_handler]
fn panic(_: &PanicInfo) -> ! { loop { core::hint::spin_loop(); } }
'''

RASPBERRY_LINKER = r'''ENTRY(_start)
SECTIONS {
  . = 0x00008000;
  .text : { *(.text._start) *(.text .text.*) *(.rodata .rodata.*) }
  .data : { *(.data .data.*) }
  .bss (NOLOAD) : { *(.bss .bss.*) *(COMMON) }
  /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.comment*) }
}
'''

X86_BOOT_SOURCE = r'''.code16
.global _start
_start:
  cli
  xorw %ax, %ax
  movw %ax, %ds
  movw $message, %si
1:
  lodsb
  testb %al, %al
  jz 2f
  outb %al, $0xe9
  jmp 1b
2:
  hlt
  jmp 2b
message:
  .asciz "AURORA_WS12_OS_HEARTBEAT"
.org 510
.word 0xaa55
'''


def _write_rust_project(path: Path, name: str, source: str, linker: str) -> None:
  (path / "src").mkdir(parents=True, exist_ok=True)
  (path / ".cargo").mkdir(parents=True, exist_ok=True)
  (path / "Cargo.toml").write_text(
    f'[package]\nname = "{name}"\nversion = "0.1.0"\nedition = "2021"\n', encoding="utf-8"
  )
  (path / "src" / "main.rs").write_text(source, encoding="utf-8")
  (path / "link.x").write_text(linker, encoding="utf-8")
  (path / ".cargo" / "config.toml").write_text(
    '[build]\nrustflags = ["-C", "link-arg=-Tlink.x", "-C", "link-arg=--nmagic"]\n',
    encoding="utf-8",
  )


def _build_rust(path: Path, target: str, name: str) -> tuple[Path | None, str]:
  cargo = shutil.which("cargo")
  if not cargo:
    return None, "cargo introuvable"
  installed = run_command(["rustup", "target", "list", "--installed"], cwd=path, timeout=20)
  if target not in installed.stdout.splitlines():
    return None, f"cible Rust {target} non installee"
  proc = run_command([cargo, "build", "--release", "--target", target], cwd=path, timeout=120)
  elf = path / "target" / target / "release" / name
  log = (proc.stdout or "") + (proc.stderr or "")
  return (elf if proc.returncode == 0 and elf.is_file() else None), log


def _elf32_to_raw(elf: Path, image: Path) -> None:
  data = elf.read_bytes()
  if data[:6] != b"\x7fELF\x01\x01":
    raise ValueError("ELF32 little-endian requis")
  program_offset = struct.unpack_from("<I", data, 28)[0]
  entry_size, entry_count = struct.unpack_from("<HH", data, 42)
  segments: list[tuple[int, bytes, int]] = []
  for index in range(entry_count):
    values = struct.unpack_from("<IIIIIIII", data, program_offset + index * entry_size)
    kind, offset, virtual, physical, file_size, memory_size, _flags, _align = values
    if kind == 1 and memory_size:
      segments.append((physical or virtual, data[offset:offset + file_size], memory_size))
  if not segments:
    raise ValueError("aucun segment ELF chargeable")
  base = min(address for address, _payload, _size in segments)
  end = max(address + size for address, _payload, size in segments)
  raw = bytearray(end - base)
  for address, payload, _size in segments:
    raw[address - base:address - base + len(payload)] = payload
  image.write_bytes(raw)


def run_renode_stage(out_dir: Path) -> dict[str, Any]:
  label = "Renode Arduino Nano 33 BLE firmware"
  renode = find_tool("AURORA_CODE_RENODE", ["renode"], ["renode-*/renode"])
  if not renode:
    return unavailable("renode_arduino_firmware", label, "embedded", "Renode introuvable")
  target = (out_dir / "renode_arduino").resolve()
  _write_rust_project(target, "aurora_ws12_nrf", NRF_SOURCE, NRF_LINKER)
  elf, build_log = _build_rust(target, "thumbv7em-none-eabi", "aurora_ws12_nrf")
  (target / "build.log").write_text(build_log, encoding="utf-8")
  if not elf:
    return unavailable("renode_arduino_firmware", label, "embedded", tail(build_log))
  renode_root = Path(renode).parent
  script = target / "run.resc"
  script.write_text(
    "\n".join([
      'mach create "aurora_ws12_arduino"',
      f'machine LoadPlatformDescription @{renode_root / "platforms/boards/arduino_nano_33_ble.repl"}',
      f'sysbus LoadELF @{elf}',
      'emulation RunFor "0.02"',
      'sysbus ReadDoubleWord 0x20000100',
      'gpio0 State',
      'quit',
    ]) + "\n",
    encoding="utf-8",
  )
  log = target / "renode.log"
  ok, returncode, console, elapsed_ms = run_until_marker(
    [renode, "--plain", "--disable-xwt", "--console", str(script)],
    cwd=renode_root,
    log_path=log,
    marker=RENODE_MARKER,
    timeout=20,
  )
  return {
    "id": "renode_arduino_firmware",
    "label": label,
    "family": "embedded",
    "status": "executed" if ok else "unavailable",
    "realExecution": ok,
    "toolPath": renode,
    "artifactPath": str(elf),
    "durationMs": elapsed_ms,
    "detail": "firmware Rust compile, charge sur nRF52840 Arduino et heartbeat RAM observe" if ok else None,
    **({} if ok else {"error": tail(console or build_log or f"renode rc={returncode}")}),
  }


def run_qemu_raspberry_stage(out_dir: Path) -> dict[str, Any]:
  label = "QEMU Raspberry Pi 2B bare-metal"
  qemu = find_tool("AURORA_CODE_QEMU_ARM", ["qemu-system-arm"], ["qemu-*/bin/qemu-system-arm"])
  if not qemu:
    return unavailable("qemu_raspberry_pi2b", label, "os_boot", "qemu-system-arm introuvable")
  target = (out_dir / "qemu_raspberry").resolve()
  _write_rust_project(target, "aurora_ws12_pi", RASPBERRY_SOURCE, RASPBERRY_LINKER)
  elf, build_log = _build_rust(target, "armv7a-none-eabi", "aurora_ws12_pi")
  (target / "build.log").write_text(build_log, encoding="utf-8")
  if not elf:
    return unavailable("qemu_raspberry_pi2b", label, "os_boot", tail(build_log))
  image = target / "kernel.img"
  try:
    _elf32_to_raw(elf, image)
  except (OSError, ValueError, struct.error) as exc:
    return unavailable("qemu_raspberry_pi2b", label, "os_boot", f"conversion ELF impossible: {exc}")
  log = target / "serial.log"
  ok, returncode, console, elapsed_ms = run_until_marker(
    [qemu, "-M", "raspi2b", "-bios", str(image), "-display", "none", "-monitor", "none", "-serial", "stdio"],
    cwd=target,
    log_path=log,
    marker=RASPBERRY_MARKER,
    timeout=12,
  )
  return {
    "id": "qemu_raspberry_pi2b",
    "label": label,
    "family": "os_boot",
    "status": "executed" if ok else "unavailable",
    "realExecution": ok,
    "toolPath": qemu,
    "artifactPath": str(image),
    "durationMs": elapsed_ms,
    "detail": "modele raspi2b demarre et heartbeat PL011 observe" if ok else None,
    **({} if ok else {"error": tail(console or f"qemu rc={returncode}")}),
  }


def run_qemu_os_stage(out_dir: Path) -> dict[str, Any]:
  label = "QEMU x86 bootable OS image"
  qemu = find_tool("AURORA_CODE_QEMU_X86", ["qemu-system-x86_64"], ["qemu-*/bin/qemu-system-x86_64"])
  assembler, linker = shutil.which("as"), shutil.which("ld")
  if not qemu or not assembler or not linker:
    return unavailable("qemu_bootable_os", label, "os_boot", "QEMU ou binutils introuvable")
  target = (out_dir / "qemu_os").resolve()
  target.mkdir(parents=True, exist_ok=True)
  source, obj, image = target / "boot.S", target / "boot.o", target / "aurora-ws12-os.img"
  source.write_text(X86_BOOT_SOURCE, encoding="utf-8")
  compile_proc = run_command([assembler, "--32", "-o", str(obj), str(source)], cwd=target, timeout=30)
  link_proc = run_command(
    [linker, "-m", "elf_i386", "-Ttext", "0x7c00", "--oformat", "binary", "-o", str(image), str(obj)],
    cwd=target,
    timeout=30,
  )
  build_log = (compile_proc.stderr or "") + (link_proc.stderr or "")
  (target / "build.log").write_text(build_log, encoding="utf-8")
  if compile_proc.returncode or link_proc.returncode or not image.is_file() or image.stat().st_size != 512:
    return unavailable("qemu_bootable_os", label, "os_boot", tail(build_log or "image boot invalide"))
  log = target / "debugcon.log"
  ok, returncode, console, elapsed_ms = run_until_marker(
    [
      qemu, "-machine", "pc", "-m", "64M", "-drive", f"file={image},format=raw,if=floppy",
      "-display", "none", "-monitor", "none", "-serial", "none", "-debugcon", "stdio", "-no-reboot",
    ],
    cwd=target,
    log_path=log,
    marker=OS_MARKER,
    timeout=12,
  )
  return {
    "id": "qemu_bootable_os",
    "label": label,
    "family": "os_boot",
    "status": "executed" if ok else "unavailable",
    "realExecution": ok,
    "toolPath": qemu,
    "artifactPath": str(image),
    "durationMs": elapsed_ms,
    "detail": "image BIOS 512 octets bootee jusqu'au heartbeat debugcon" if ok else None,
    **({} if ok else {"error": tail(console or f"qemu rc={returncode}")}),
  }
