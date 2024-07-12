import sys
import subprocess
import ctypes
import os


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def run_script_in_new_console(script_path):
    # Open a new console window and run the script
    subprocess.Popen(['start', 'cmd', '/K', sys.executable, script_path], shell=True)


if is_admin():
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
    run_script_in_new_console(script_path)
else:
    # Re-run the program with admin rights
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, __file__, None, 1)
