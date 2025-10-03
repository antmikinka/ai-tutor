#!/usr/bin/env python3
"""
🚀 AI Math Tutor - Python Startup Script
Production-ready startup script with all critical issues resolved
"""

import os
import sys
import subprocess
import time
import threading
import requests
import signal
import atexit
from pathlib import Path

# Configuration
BACKEND_PORT = 8000
FRONTEND_DELAY = 8  # Seconds to wait for backend before starting frontend
VENV_PATH = "venv"
PYTHON_EXE = os.path.join(VENV_PATH, "Scripts", "python.exe") if os.name == 'nt' else os.path.join(VENV_PATH, "bin", "python")

# Color codes for terminal output
class Colors:
    GREEN = '\033[92m'
    CYAN = '\033[96m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header():
    """Print the startup header"""
    print(f"\n{Colors.BOLD}{Colors.GREEN}🎯 AI Math Tutor - Production Startup{Colors.END}")
    print(f"{Colors.BOLD}{Colors.GREEN}========================================{Colors.END}\n")

def print_step(message, color=Colors.CYAN):
    """Print a step message"""
    print(f"{color}{message}{Colors.END}")

def print_success(message):
    """Print a success message"""
    print(f"{Colors.GREEN}✅ {message}{Colors.END}")

def print_error(message):
    """Print an error message"""
    print(f"{Colors.RED}❌ {message}{Colors.END}")

def print_info(message):
    """Print an info message"""
    print(f"{Colors.BLUE}ℹ️  {message}{Colors.END}")

def print_warning(message):
    """Print a warning message"""
    print(f"{Colors.YELLOW}⚠️  {message}{Colors.END}")

def check_requirements():
    """Check if system requirements are met"""
    print_step("🔍 Checking system requirements...")

    # Check if virtual environment exists
    if not os.path.exists(PYTHON_EXE):
        print_error("Virtual environment not found!")
        print_info("Please run setup first to create virtual environment")
        return False

    # Check if Python works in venv
    try:
        result = subprocess.run([PYTHON_EXE, "-c", "import fastapi, uvicorn, websockets"],
                              capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            print_error("Missing dependencies!")
            print_info("Please install dependencies first")
            return False
    except Exception as e:
        print_error(f"Python virtual environment issue: {e}")
        return False

    print_success("System requirements verified")
    return True

def test_backend_ready(port):
    """Test if backend is ready"""
    try:
        response = requests.get(f"http://localhost:{port}/health", timeout=2)
        return response.status_code == 200
    except:
        return False

def start_backend(port):
    """Start the backend server"""
    print_step(f"🐍 Starting AI Math Tutor Backend...")
    print_info(f"   Port: {port}")
    print_info(f"   Mode: Lazy Loading")

    # Change to backend directory
    os.chdir("src/backend")

    # Start backend process
    backend_cmd = [os.path.join("..", "..", PYTHON_EXE), "-m", "uvicorn",
                   "main:app", "--host", "localhost", "--port", str(port), "--reload"]

    try:
        backend_process = subprocess.Popen(backend_cmd, stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT, text=True)

        # Return to original directory
        os.chdir("../..")

        return backend_process
    except Exception as e:
        print_error(f"Failed to start backend: {e}")
        os.chdir("../..")  # Ensure we return to original directory
        return None

def start_frontend():
    """Start the Electron frontend"""
    print_step("⚛️  Starting AI Math Tutor Desktop App...")
    print_info("   UI loads immediately (< 3 seconds)")
    print_info("   Models load in background (lazy loading)")

    # Start Electron app in development mode
    try:
        if os.name == 'nt':
            # Windows - start in new window with development mode
            subprocess.Popen(["start", "cmd", "/k", "npm run electron:dev"], shell=True)
        else:
            # macOS/Linux
            subprocess.Popen(["npm", "run", "electron:dev"], shell=True)

        print_success("Electron app started in development mode")
        print_info("   Note: First startup may take a moment to load dependencies")
        return True
    except Exception as e:
        print_error(f"Failed to start frontend: {e}")
        return False

def monitor_backend(process):
    """Monitor backend process and output logs"""
    print_step("📊 Monitoring backend logs...")
    print_info("   Press Ctrl+C to stop monitoring")

    try:
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                print(f"{Colors.CYAN}Backend: {output.strip()}{Colors.END}")
            time.sleep(0.1)
    except KeyboardInterrupt:
        print_warning("Monitoring stopped")
    except Exception as e:
        print_error(f"Monitoring error: {e}")

def cleanup_processes(processes):
    """Clean up all processes"""
    print_step("🧹 Cleaning up processes...")

    for process in processes:
        if process and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=5)
            except:
                try:
                    process.kill()
                except:
                    pass

    print_success("Cleanup completed")

def main():
    """Main startup function"""
    print_header()

    # Store processes for cleanup
    processes = []

    # Register cleanup function
    def cleanup():
        cleanup_processes(processes)

    atexit.register(cleanup)
    signal.signal(signal.SIGINT, lambda s, f: cleanup() or sys.exit(0))
    signal.signal(signal.SIGTERM, lambda s, f: cleanup() or sys.exit(0))

    try:
        # Check requirements
        if not check_requirements():
            sys.exit(1)

        print()

        # Start backend
        backend_process = start_backend(BACKEND_PORT)
        if not backend_process:
            sys.exit(1)

        processes.append(backend_process)
        print()

        # Wait for backend to be ready
        print_step("⏳ Waiting for backend to start...")
        backend_ready = False
        attempts = 0
        max_attempts = 30

        while not backend_ready and attempts < max_attempts:
            print_info(f"   Attempt {attempts + 1}/{max_attempts}...")
            time.sleep(2)
            backend_ready = test_backend_ready(BACKEND_PORT)
            attempts += 1

        if not backend_ready:
            print_error("Backend failed to start!")
            print_info("Check backend logs for errors")
            sys.exit(1)

        print_success("Backend is ready!")
        print_info(f"   URL: http://localhost:{BACKEND_PORT}")
        print_info(f"   API Docs: http://localhost:{BACKEND_PORT}/api/docs")
        print()

        # Start frontend
        if not start_frontend():
            sys.exit(1)

        print()
        print_success("🎉 AI Math Tutor is starting successfully!")
        print()
        print_step("📋 Key Features:")
        print_success("   Immediate UI access")
        print_success("   Models load in background when needed")
        print_success("   Graceful fallback when models unavailable")
        print_success("   Real-time drawing and math solving")
        print_success("   Voice interaction capabilities")
        print()
        print_step("🌐 Access Points:")
        print_info(f"   Backend: http://localhost:{BACKEND_PORT}")
        print_info(f"   Health: http://localhost:{BACKEND_PORT}/health")
        print_info(f"   API: http://localhost:{BACKEND_PORT}/api/docs")
        print()
        print_step("💡 Usage Tips:")
        print("   • Drawing board appears immediately")
        print("   • Settings panel is accessible right away")
        print("   • AI models load automatically when you solve problems")
        print("   • Voice features work when you enable them")
        print()
        print_warning("🛑 To stop: Press Ctrl+C")
        print_warning("🔄 To restart: Run this script again")
        print()

        # Start monitoring backend in a separate thread
        monitor_thread = threading.Thread(target=monitor_backend, args=(backend_process,))
        monitor_thread.daemon = True
        monitor_thread.start()

        # Keep main thread alive
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print_warning("\n🛑 Shutdown requested...")
            cleanup()
            print_success("AI Math Tutor stopped successfully")

    except Exception as e:
        print_error(f"Startup failed: {e}")
        cleanup()
        sys.exit(1)

if __name__ == "__main__":
    main()