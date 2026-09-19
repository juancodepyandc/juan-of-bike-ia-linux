import pty, os, select, subprocess, threading

def run(cmd):
    master, slave = pty.openpty()
    proc = subprocess.Popen(cmd, shell=True, stdout=slave, stderr=slave, close_fds=True)
    os.close(slave)
    
    result_str = ""
    while True:
        r, _, _ = select.select([master], [], [], 0.1)
        if master in r:
            try:
                chunk = os.read(master, 1024).decode('utf-8', errors='replace')
                if not chunk: break
                result_str += chunk
            except OSError:
                break
        elif proc.poll() is not None:
            break
    os.close(master)
    print(f"Output of '{cmd}': {repr(result_str)}")

threading.Thread(target=run, args=("whoami",)).start()
threading.Thread(target=run, args=("ls -la",)).start()
