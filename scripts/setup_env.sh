#!/bin/bash
# ==============================================================================
# Environment Setup Script
# ==============================================================================
# This script helps set up local development environment for Algo-Trade
# Usage: ./scripts/setup_env.sh
# ==============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "$1"
}

# ==============================================================================
# Step 1: Check Prerequisites
# ==============================================================================
print_info "\n=== Step 1: Checking Prerequisites ===\n"

# Check Python version
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | awk '{print $2}')
    print_success "Python3 found: $PYTHON_VERSION"

    # Check if version >= 3.9
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

    if [ "$PYTHON_MAJOR" -lt 3 ] || [ "$PYTHON_MINOR" -lt 9 ]; then
        print_error "Python 3.9+ required, found $PYTHON_VERSION"
        exit 1
    fi
else
    print_error "Python3 not found. Please install Python 3.9+"
    exit 1
fi

# Check Docker (optional)
if command -v docker &> /dev/null; then
    print_success "Docker found: $(docker --version)"
else
    print_warning "Docker not found (optional, needed for Kafka)"
fi

# Check git
if command -v git &> /dev/null; then
    print_success "Git found: $(git --version)"
else
    print_error "Git not found. Please install git"
    exit 1
fi

# ==============================================================================
# Step 2: Environment File Setup
# ==============================================================================
print_info "\n=== Step 2: Setting Up Environment File ===\n"

if [ -f .env ]; then
    print_warning ".env file already exists"
    read -p "Overwrite? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Keeping existing .env file"
    else
        cp .env.example .env
        print_success "Created .env from .env.example"
    fi
else
    cp .env.example .env
    print_success "Created .env from .env.example"
fi

# Set restrictive permissions
chmod 600 .env
print_success "Set .env permissions to 600 (owner read/write only)"

# ==============================================================================
# Step 3: Configure Environment
# ==============================================================================
print_info "\n=== Step 3: Configuring Environment ===\n"

# Prompt for environment type
print_info "Select environment type:"
echo "1) Development (local, paper trading)"
echo "2) Staging (paper trading with Vault)"
echo "3) Production (MANUAL SETUP REQUIRED)"
read -p "Enter choice [1]: " ENV_CHOICE
ENV_CHOICE=${ENV_CHOICE:-1}

case $ENV_CHOICE in
    1)
        # Development environment
        print_info "Configuring for DEVELOPMENT..."

        # Update .env file
        sed -i.bak 's/^ENVIRONMENT=.*/ENVIRONMENT=development/' .env
        sed -i.bak 's/^LOG_LEVEL=.*/LOG_LEVEL=DEBUG/' .env
        sed -i.bak 's/^IBKR_PORT=.*/IBKR_PORT=4002/' .env
        sed -i.bak 's/^IBKR_READ_ONLY=.*/IBKR_READ_ONLY=true/' .env
        sed -i.bak 's/^DP_USE_VAULT=.*/DP_USE_VAULT=0/' .env
        sed -i.bak 's/^ENABLE_PAPER_TRADING=.*/ENABLE_PAPER_TRADING=true/' .env
        sed -i.bak 's/^ENABLE_LIVE_TRADING=.*/ENABLE_LIVE_TRADING=false/' .env

        rm -f .env.bak

        print_success "Development environment configured"
        print_warning "IMPORTANT: Get your paper trading account from IBKR"
        print_warning "Update IBKR_ACCOUNT in .env with your DU* account number"
        ;;

    2)
        # Staging environment
        print_info "Configuring for STAGING..."

        sed -i.bak 's/^ENVIRONMENT=.*/ENVIRONMENT=staging/' .env
        sed -i.bak 's/^LOG_LEVEL=.*/LOG_LEVEL=INFO/' .env
        sed -i.bak 's/^IBKR_PORT=.*/IBKR_PORT=4002/' .env
        sed -i.bak 's/^IBKR_READ_ONLY=.*/IBKR_READ_ONLY=true/' .env
        sed -i.bak 's/^DP_USE_VAULT=.*/DP_USE_VAULT=1/' .env
        sed -i.bak 's/^ENABLE_PAPER_TRADING=.*/ENABLE_PAPER_TRADING=true/' .env
        sed -i.bak 's/^ENABLE_LIVE_TRADING=.*/ENABLE_LIVE_TRADING=false/' .env

        rm -f .env.bak

        print_success "Staging environment configured"
        print_warning "IMPORTANT: Configure Vault credentials:"
        print_warning "  - Set VAULT_ADDR in .env"
        print_warning "  - Set VAULT_TOKEN in .env"
        print_warning "  - See SECRETS_MANAGEMENT.md for setup"
        ;;

    3)
        print_error "Production setup requires manual configuration!"
        print_info "Please follow SECRETS_MANAGEMENT.md for production setup"
        print_info "Key steps:"
        print_info "  1. Setup HashiCorp Vault or AWS Secrets Manager"
        print_info "  2. Store IBKR live credentials in Vault"
        print_info "  3. Configure Vault authentication (AppRole)"
        print_info "  4. Test in staging first!"
        print_info "  5. Get CTO approval (see PRE_LIVE_CHECKLIST.md)"
        exit 0
        ;;

    *)
        print_error "Invalid choice"
        exit 1
        ;;
esac

# ==============================================================================
# Step 4: Create Required Directories
# ==============================================================================
print_info "\n=== Step 4: Creating Directories ===\n"

mkdir -p logs
mkdir -p data
mkdir -p backups
mkdir -p reports
mkdir -p incidents

print_success "Created required directories"

# ==============================================================================
# Step 5: Install Dependencies
# ==============================================================================
print_info "\n=== Step 5: Installing Dependencies ===\n"

read -p "Install Python dependencies? (Y/n): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    if [ -f requirements.txt ]; then
        pip install -r requirements.txt
        print_success "Python dependencies installed"
    else
        print_warning "requirements.txt not found, skipping"
    fi
fi

# ==============================================================================
# Step 6: Verify Setup
# ==============================================================================
print_info "\n=== Step 6: Verifying Setup ===\n"

# Check .env file
if [ -f .env ]; then
    print_success ".env file exists"

    # Check if .env is gitignored
    if git check-ignore .env > /dev/null 2>&1; then
        print_success ".env is gitignored (safe)"
    else
        print_error ".env is NOT gitignored! Add it to .gitignore immediately!"
    fi
else
    print_error ".env file not found"
fi

# Check required directories
REQUIRED_DIRS=("logs" "data" "backups" "reports" "incidents")
for dir in "${REQUIRED_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        print_success "Directory $dir/ exists"
    else
        print_error "Directory $dir/ not found"
    fi
done

# Test environment loading
print_info "\nTesting environment variable loading..."
python3 -c "
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env
load_dotenv()

# Check key variables
vars_to_check = [
    'ENVIRONMENT',
    'IBKR_HOST',
    'IBKR_PORT',
    'KAFKA_BOOTSTRAP_SERVERS'
]

all_ok = True
for var in vars_to_check:
    value = os.getenv(var)
    if value:
        print(f'✓ {var}={value}')
    else:
        print(f'✗ {var} not set')
        all_ok = False

if all_ok:
    print('\n✓ Environment loaded successfully')
else:
    print('\n✗ Some variables not set - check .env file')
" 2>/dev/null

if [ $? -eq 0 ]; then
    print_success "Environment variables loaded successfully"
else
    print_warning "python-dotenv not installed, install with: pip install python-dotenv"
fi

# ==============================================================================
# Step 7: Next Steps
# ==============================================================================
print_info "\n=== Setup Complete! ===\n"

print_info "Next steps:\n"
print_info "1. Edit .env file with your configuration:"
print_info "   - Set IBKR_ACCOUNT to your paper trading account (DU*)"
print_info "   - Adjust other settings as needed\n"

print_info "2. Start Kafka (if using Docker):"
print_info "   docker-compose up -d zookeeper kafka\n"

print_info "3. Start TWS or IB Gateway in paper trading mode:"
print_info "   - Configure to listen on port 4002 (paper) or 7497 (TWS paper)"
print_info "   - Enable API connections in settings\n"

print_info "4. Run the system (see RUNBOOK.md):"
print_info "   python -m data_plane.app.main\n"

print_info "5. Read the documentation:"
print_info "   - RUNBOOK.md - Start/stop procedures"
print_info "   - SECRETS_MANAGEMENT.md - Secrets handling"
print_info "   - INCIDENT_PLAYBOOK.md - Incident response"
print_info "   - RACI.md - Responsibilities\n"

print_info "For production deployment:"
print_info "   - See PRE_LIVE_CHECKLIST.md"
print_info "   - Complete all validation gates"
print_info "   - Get CTO approval\n"

print_success "Environment setup complete!"
