"""
Quick Start Script for Autonomous Insurance Claims Processor
=============================================================
Run this to initialize and start the application.
"""
import os
import sys
import subprocess
from pathlib import Path

# Colors for output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    END = '\033[0m'

def print_header(text):
    print(f"\n{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BLUE}{text.center(60)}{Colors.END}")
    print(f"{Colors.BLUE}{'='*60}{Colors.END}\n")

def print_success(text):
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")

def print_warning(text):
    print(f"{Colors.YELLOW}⚠ {text}{Colors.END}")

def print_error(text):
    print(f"{Colors.RED}✗ {text}{Colors.END}")

def check_python_version():
    """Check Python version."""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 11):
        print_error(f"Python 3.11+ required. Found: {version.major}.{version.minor}")
        return False
    print_success(f"Python version: {version.major}.{version.minor}.{version.micro}")
    return True

def check_env_file():
    """Check if .env file exists."""
    env_path = Path("autonomous_claims_processor/.env")
    if not env_path.exists():
        print_warning(".env file not found. Copy from .env.example")
        example_path = Path("autonomous_claims_processor/.env.example")
        if example_path.exists():
            import shutil
            shutil.copy(example_path, env_path)
            print_success("Created .env from .env.example")
            print_warning("Please edit .env and add your API keys!")
            return False
    else:
        print_success(".env file found")
        # Check for required keys
        with open(env_path, 'r') as f:
            content = f.read()
        required = ['OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'PINECONE_API_KEY']
        missing = []
        for key in required:
            if key + '=' not in content or key + '=your' in content or key + '=sk-' not in content:
                missing.append(key)
        if missing:
            print_warning(f"Missing/Invalid API keys: {', '.join(missing)}")
            return False
    return True

def install_dependencies():
    """Install Python dependencies."""
    print_header("Installing Dependencies")
    
    requirements = Path("requirements.txt")
    if not requirements.exists():
        print_error("requirements.txt not found!")
        return False
    
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(requirements)])
        print_success("Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError:
        print_error("Failed to install dependencies")
        return False

def check_database():
    """Check PostgreSQL connection."""
    print_header("Database Check")
    print_warning("Ensure PostgreSQL is running and accessible")
    print("Connection string: postgresql://postgres:password@localhost:5432/insurance_claims_db")
    return True

def start_application():
    """Start the FastAPI application."""
    print_header("Starting Application")
    
    try:
        import uvicorn
        from autonomous_claims_processor.core.settings import settings
        
        print(f"Starting server on {settings.app_host}:{settings.app_port}")
        print(f"Swagger UI: http://{settings.app_host}:{settings.app_port}/docs")
        print(f"ReDoc: http://{settings.app_host}:{settings.app_port}/redoc")
        print("\nPress Ctrl+C to stop\n")
        
        uvicorn.run(
            "autonomous_claims_processor.api.app:app",
            host=settings.app_host,
            port=settings.app_port,
            reload=settings.app_debug
        )
    except ImportError:
        print_error("uvicorn not installed. Run: pip install uvicorn")
    except Exception as e:
        print_error(f"Error starting application: {str(e)}")

def main():
    """Main setup and run function."""
    print_header("AUTONOMOUS INSURANCE CLAIMS PROCESSOR")
    print("ClaimOS - AI-Powered Claims Processing System")
    
    # Check Python version
    print_header("System Checks")
    if not check_python_version():
        sys.exit(1)
    
    # Check environment file
    env_ready = check_env_file()
    
    # Ask to install dependencies
    print_header("Dependencies")
    install = input("Install Python dependencies? (y/n): ").lower().strip()
    if install == 'y':
        if not install_dependencies():
            sys.exit(1)
    
    # Database check
    check_database()
    
    # Start application
    print_header("Ready to Start")
    if not env_ready:
        print_warning("Please configure your .env file before starting!")
        return
    
    start = input("Start the application? (y/n): ").lower().strip()
    if start == 'y':
        start_application()
    else:
        print("\nYou can start the application manually with:")
        print("  python -m uvicorn autonomous_claims_processor.api.app:app --reload")
        print("\nor run the Docker setup:")
        print("  docker-compose up -d")

if __name__ == "__main__":
    main()
