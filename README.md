# Telegram Server Administration Bot

[Español](README.es.md) | [**English**]

A powerful and secure Python-based Telegram bot designed to monitor and manage Linux servers directly from your mobile device. It integrates system tools, network utilities, service management, Docker, Fail2Ban, and Google's Gemini API for intelligent analysis.

---

## ✨ Features

- **💻 System Monitoring**:
  - General status of services and ports (`/status`).
  - Real-time resource usage (CPU, RAM, Load Average) (`/resources`).
  - Disk usage (`/disk`).
  - Process list (`/processes`).
  - System and distribution information (`/systeminfo`).

- **🛡️ Security & Administration**:
  - **Secure Script Execution**: Run pre-configured `.sh` and `.py` scripts, with SHA256 hash verification to prevent unauthorized execution.
  - **Service Management**: Start, stop, restart, and check the status of system services (e.g., `nginx`, `mysql`) using `systemctl`.
  - **Fail2Ban Management**: Check jail statuses and unban IPs directly from the bot.
  - **Cron Job Management**: View scheduled tasks.
  - **User Management**: Authorization system with a super admin and authorized users.

- **🐳 Docker Management**:
  - List active containers (`docker ps`).
  - Restart allowed containers.
  - View logs from a container.

- **🌐 Network Tools**:
  - `ping`, `traceroute`, `nmap -A`, `dig`, `whois`.

- **🤖 AI Integration (Google Gemini)**:
  - `/ask`: Make quick queries to the Gemini Flash model.
  - `/askpro`: Make complex queries to the Gemini Pro model (super admin only).
  - `/analyze`: Ask the AI to analyze monitoring data and provide recommendations.

- **📁 File Management**:
  - Upload files and images directly to the server via chat.
  - Download files from the server to the chat using the `/get` command.

- **🔔 Alerts & Utilities**:
  - Periodic log monitoring with pattern-based alerts.
  - Alerts for high CPU and disk usage thresholds.
  - Reminder system (`/remind`).
  - Multi-language support (Spanish & English).

---

## 🚀 Setup and Installation

#### 1. Prerequisites
- A Linux server (tested on Debian/Ubuntu).
- Python 3.10 or higher.
- System tools installed: `ping`, `traceroute`, `nmap`, `dig`, `whois`, `fortune`, `ansiweather`.
  ```bash
  sudo apt update
  sudo apt install dnsutils nmap whois fortune ansiweather
  ```

#### 2. Clone and Prepare the Environment
```bash
# Clone the repository (or copy the files)
git clone [https://your-repository.git](https://your-repository.git)
cd your-repository

# (Optional but recommended) Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt
```

#### 3. File Configuration
Create the following directory structure for secrets:
```bash
sudo mkdir -p /etc/telegram-bot
sudo chown $USER:$USER /etc/telegram-bot
```

- **`bot.env`** (Secrets file): Create this file at `/etc/telegram-bot/bot.env`.
  ```env
  # Your Telegram bot token from @BotFather
  TELEGRAM_TOKEN=12345:ABC...

  # Your Google Gemini API Key (optional, for AI features)
  GEMINI_API_KEY=AIzaSy...
  ```

- **`users.json`**: Place this file in the same directory as the bot. It contains the IDs of authorized users.
  ```json
  {
    "super_admin_id": 123456789,
    "authorized_users": [
      123456789,
      987654321
    ]
  }
  ```

- **`configbot.json`**: This is the main configuration file. Review and adjust it to your needs (script paths, allowed services, etc.).

#### 4. Security Configuration

- **`sudo` Permissions**: To allow the bot to manage services and Docker without a password, add a rule using `sudo visudo`:
  ```sudoers
  # Replace 'your_user' with the user that will run the bot
  your_user ALL=(root) NOPASSWD: /bin/systemctl start *, /bin/systemctl stop *, /bin/systemctl restart *, /bin/docker restart *
  ```

- **Seal Scripts**: For security, the bot will only execute scripts whose hash matches the one stored in `configbot.json`. To generate or update these hashes, run:
  ```bash
  python3 seal_scripts.py
  ```
  You must run this command the first time you set up your scripts, and every time you modify them.

#### 5. Run the Bot
You can run it directly or, preferably, as a `systemd` service.
```bash
# Direct execution
python3 bot_interactivo.py
```

---

## 🛠️ Usage
- Send `/start` to the bot to see the main menu.
- Most functions are accessible via the menu buttons.
- Use `/help` for a complete list of available text commands.

---

## 📄 License
This project is licensed under the MIT License.
