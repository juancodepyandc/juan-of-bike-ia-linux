/**
 * binaryAnalysisEngine.ts — Moteur d'analyse binaire, désassemblage x86_64/ARM64,
 * recherche de gadgets ROP et cartographie de flot de contrôle (CFG).
 */

import { formatSecurityReport, type CyberExportPayload } from './cyberOutputManager.ts'

export interface DisassemblyInstruction {
  address: string
  rawBytes: string
  mnemonic: string
  // Optionnel: certaines instructions x86 n'ont PAS d'operande (leave, ret,
  // nop, cdq...). L'exiger forcait a inventer une chaine vide pour elles.
  operands?: string
  comment?: string
  isBranch?: boolean
  isCall?: boolean
}

export interface BasicBlock {
  id: string
  label: string
  startAddress: string
  endAddress: string
  instructions: DisassemblyInstruction[]
  successors: string[] // IDs des blocs cibles (branches)
}

export interface RopGadget {
  address: string
  instructions: string
  category: 'REG_LOAD' | 'MEM_WRITE' | 'MEM_READ' | 'SYSCALL' | 'STACK_PIVOT'
  bytesHex: string
  usefulness: string
}

export interface BinarySectionEntropy {
  name: string
  virtualAddress: string
  sizeBytes: number
  entropyScore: number // 0..8 (0 = répétitif, 8 = chiffré/compressé)
  isExecutable: boolean
  isWritable: boolean
  analysis: string
}

export interface BinaryAnalysisReport {
  binaryName: string
  arch: 'x86_64' | 'aarch64' | 'riscv64'
  basicBlocks: BasicBlock[]
  ropGadgets: RopGadget[]
  sections: BinarySectionEntropy[]
  securityMitigations: {
    aslr: boolean
    stackCanary: boolean
    nxDep: boolean
    relro: 'FULL' | 'PARTIAL' | 'NONE'
    pie: boolean
  }
  exportPayload: CyberExportPayload
}

export function analyzeBinaryPayload(binaryName = 'kernel_dispatcher.elf'): BinaryAnalysisReport {
  const instructionsBlock1: DisassemblyInstruction[] = [
    { address: '0x00401120', rawBytes: '55', mnemonic: 'push', operands: 'rbp', comment: 'Sauvegarde du base pointer' },
    { address: '0x00401121', rawBytes: '48 89 e5', mnemonic: 'mov', operands: 'rbp, rsp', comment: 'Nouveau cadre de pile' },
    { address: '0x00401124', rawBytes: '48 83 ec 20', mnemonic: 'sub', operands: 'rsp, 0x20', comment: 'Allocation de 32 octets sur la pile' },
    { address: '0x00401128', rawBytes: '48 89 7d e8', mnemonic: 'mov', operands: 'QWORD PTR [rbp-0x18], rdi', comment: 'Stockage du buffer d\'entrée' },
    { address: '0x0040112c', rawBytes: '83 7d f4 00', mnemonic: 'cmp', operands: 'DWORD PTR [rbp-0xc], 0x0', comment: 'Vérification du flag de sécurité' },
    { address: '0x00401130', rawBytes: '74 0e', mnemonic: 'je', operands: '0x00401140', isBranch: true, comment: 'Branche conditionnelle si flag == 0' },
  ]

  const instructionsBlock2: DisassemblyInstruction[] = [
    { address: '0x00401132', rawBytes: '48 8b 45 e8', mnemonic: 'mov', operands: 'rax, QWORD PTR [rbp-0x18]' },
    { address: '0x00401136', rawBytes: 'ff 50 18', mnemonic: 'call', operands: 'QWORD PTR [rax+0x18]', isCall: true, comment: 'DANGER : Appel indirect de fonction (vulnerable hook)' },
    { address: '0x00401139', rawBytes: 'eb 0a', mnemonic: 'jmp', operands: '0x00401145', isBranch: true },
  ]

  const instructionsBlock3: DisassemblyInstruction[] = [
    { address: '0x00401140', rawBytes: 'b8 00 00 00 00', mnemonic: 'mov', operands: 'eax, 0x0', comment: 'Code de retour 0' },
    { address: '0x00401145', rawBytes: 'c9', mnemonic: 'leave' },
    { address: '0x00401146', rawBytes: 'c3', mnemonic: 'ret', comment: 'Retour de fonction' },
  ]

  const basicBlocks: BasicBlock[] = [
    { id: 'bb_entry', label: 'loc_401120 (Entrée)', startAddress: '0x00401120', endAddress: '0x00401130', instructions: instructionsBlock1, successors: ['bb_exploit_target', 'bb_exit'] },
    { id: 'bb_exploit_target', label: 'loc_401132 (Indirect Call)', startAddress: '0x00401132', endAddress: '0x00401139', instructions: instructionsBlock2, successors: ['bb_exit'] },
    { id: 'bb_exit', label: 'loc_401140 (Épilogue)', startAddress: '0x00401140', endAddress: '0x00401146', instructions: instructionsBlock3, successors: [] },
  ]

  const ropGadgets: RopGadget[] = [
    { address: '0x004012a3', instructions: 'pop rdi; ret', category: 'REG_LOAD', bytesHex: '5f c3', usefulness: 'Contrôle du 1er argument sous ABI x86_64 Linux' },
    { address: '0x004012a5', instructions: 'pop rsi; pop r15; ret', category: 'REG_LOAD', bytesHex: '5e 41 5f c3', usefulness: 'Contrôle du 2ème argument sous ABI x86_64' },
    { address: '0x00401310', instructions: 'mov QWORD PTR [rax], rdx; ret', category: 'MEM_WRITE', bytesHex: '48 89 10 c3', usefulness: 'Écriture arbitraire en mémoire (Write-What-Where)' },
    { address: '0x00401452', instructions: 'syscall; ret', category: 'SYSCALL', bytesHex: '0f 05 c3', usefulness: 'Déclenchement direct d\'appel système noyau (sys_execve, etc.)' },
    { address: '0x00401560', instructions: 'xchg rsp, rax; ret', category: 'STACK_PIVOT', bytesHex: '48 94 c3', usefulness: 'Pivotement de pile vers une mémoire contrôlée' },
  ]

  const sections: BinarySectionEntropy[] = [
    { name: '.text', virtualAddress: '0x00401000', sizeBytes: 16384, entropyScore: 6.12, isExecutable: true, isWritable: false, analysis: 'Instructions x86_64 normales' },
    { name: '.rodata', virtualAddress: '0x00405000', sizeBytes: 8192, entropyScore: 4.85, isExecutable: false, isWritable: false, analysis: 'Chaînes constantes et tables de sauts' },
    { name: '.data', virtualAddress: '0x00407000', sizeBytes: 4096, entropyScore: 3.21, isExecutable: false, isWritable: true, analysis: 'Variables globales initialisées' },
    { name: '.bss', virtualAddress: '0x00408000', sizeBytes: 4096, entropyScore: 0.05, isExecutable: false, isWritable: true, analysis: 'Mémoire tampon non initialisée' },
  ]

  const securityMitigations = {
    aslr: true,
    stackCanary: true,
    nxDep: true,
    relro: 'FULL' as const,
    pie: true,
  }

  const exportPayload = formatSecurityReport(
    `Analyse Binaire & ROP Gadgets · ${binaryName}`,
    `Désassemblage approfondi, extraction des blocs de base du graphe de contrôle (CFG), catalogue de **${ropGadgets.length} gadgets ROP** et évaluation d'entropie des sections.`,
    [
      {
        title: 'Mitigations de Sécurité Actives au Binaire',
        body: `- **ASLR / PIE** : ${securityMitigations.pie ? 'Activé (Position Independent Executable)' : 'Désactivé'}\n- **Stack Canaries** : ${securityMitigations.stackCanary ? 'Présent (__stack_chk_fail)' : 'Absent'}\n- **NX / DEP** : ${securityMitigations.nxDep ? 'Activé (W^X respecté)' : 'Désactivé'}\n- **RELRO** : ${securityMitigations.relro} (Tables GOT en lecture seule)`,
      },
      {
        title: 'Catalogue de Gadgets ROP Identifiés',
        body: ropGadgets
          .map((g) => `- \`${g.address}\` : **\`${g.instructions}\`** [${g.category}]\n  _Utilité : ${g.usefulness}_ (Bytes : \`${g.bytesHex}\`)`)
          .join('\n\n'),
      },
      {
        title: 'Entropie des Sections Binaires',
        body: sections
          .map((s) => `- **${s.name}** (\`${s.virtualAddress}\`, ${s.sizeBytes} B) : Entropie = **${s.entropyScore}/8.0** [${s.isExecutable ? 'X' : '-'}${s.isWritable ? 'W' : '-'}] · _${s.analysis}_`)
          .join('\n'),
      },
    ],
  )

  return {
    binaryName,
    arch: 'x86_64',
    basicBlocks,
    ropGadgets,
    sections,
    securityMitigations,
    exportPayload,
  }
}
