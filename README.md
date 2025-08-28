# Telegram Server Administration Bot

[Español](README.es.md) | [**English**]

A powerful and secure Python-based Telegram bot designed to monitor and manage Linux servers directly from your mobile device. It integrates system tools, network utilities, service management, Docker, Fail2Ban, and Google's Gemini API for intelligent analysis.

# SysAdmin Telegram Bot

## ✨ Key Features

This bot is designed to be a Swiss army knife for system administrators, offering a wide range of features accessible from anywhere via Telegram.

### 📊 Monitoring & Status

- **Interactive Menu**: A clean, button-based interface for easy navigation.
- **Overall Status**: Checks the status (ping, ports, SSL) of multiple servers defined in the configuration.
- **System Resources**: Fetches real-time reports on CPU, average load, RAM, and disk usage.
- **Service Management**: Checks, starts, stops, and restarts system services (`systemd`).
- **Log Viewer**: Reads the latest lines from pre-configured logs and searches for patterns within them.

### 🛠️ Administration & Tools

- **Script Execution**: Securely runs pre-authorized `shell` (.sh) and `python` (.py) scripts.
- **Docker Management**: Lists active containers, views their logs, and restarts them.
- **Network Tools**: Executes `ping`, `traceroute`, `nmap`, `dig`, and `whois` on defined targets.
- **Backup Management**: Triggers backup scripts directly from the bot.
- **Cron Viewer**: Displays the scheduled tasks (`crontab`) for the bot's user.
- **Advanced Tools**: Includes commands for in-depth log analysis, file inspection, and advanced network diagnostics.

### 🛡️ Security

- **Access Control**: A multi-level authorization system with a `super_admin_id` and a list of `authorized_users`.
- **Fail2Ban Integration**: Checks the status of jails and allows for unbanning IP addresses.
- **Script Sealing**: A security mechanism that stores and verifies the `SHA256` hash of each script before execution, preventing unauthorized code modifications.
- **Input Validation**: Sanitizes and validates all user inputs to prevent attacks (e.g., path traversal, command injection).

### 🤖 AI Integration (Google Gemini)

- **/ask**: Ask general-purpose questions to a fast model (Gemini Flash).
- **/askpro**: (Super Admin only) Ask complex queries to a more advanced model (Gemini Pro).
- **/analyze**: Asks the AI to analyze system data (`status`, `resources`, `disk`) and provide a diagnosis or recommendations.

### ⚙️ Utilities & Customization

- **File Management**: Upload files and photos to the server and download files from pre-configured directories.
- **Multi-language**: Support for multiple languages (Spanish and English by default) thanks to `gettext`.
- **Reminders**: Set reminders (`/remind "text" in 1d 2h`) with a job queue system.
- **Persistence**: Saves the user's selected language and other data across bot restarts.
- **Other Utilities**: Includes fun commands like `/fortune` and a weather forecast feature.

-----

## 🚀 Installation & Setup

Follow these steps to configure and launch your own bot.

### 1. Prerequisites

- Python 3.8 or higher.
- A Telegram Bot Token (obtained from [@BotFather](https://t.me/BotFather)).
- (Optional) A Google Gemini API Key.

### 2. Clone and Prepare the Environment

```bash
# Clone the repository
git clone [https://github.com/Sabbat-cloud/telegram-admin-bot](https://github.com/Sabbat-cloud/telegram-admin-bot)
cd telegram-admin-bot

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install the dependencies
pip install -r requirements.txt
````

### 3\. File Configuration

The bot uses a centralized and secure configuration setup.

**a) Secrets (`/etc/telegram-bot/bot.env`)**

Create a file in a secure location (outside the repository) to store your credentials.

```ini
# /etc/telegram-bot/bot.env
TELEGRAM_TOKEN="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
GEMINI_API_KEY="YourOptionalGeminiApiKey"
```

**b) Users (`users.json`)**

Create this file in the bot's main directory to define who can use it.

```json
{
  "super_admin_id": 123456789,
  "authorized_users": [
    123456789,
    987654321
  ]
}
```

> **Note**: You can get your Telegram ID by talking to bots like [@userinfobot](https://t.me/userinfobot).

**c) Main Configuration (`configbot.json`)**

This is the heart of the configuration. Adapt the servers, logs, and other options to your needs. Scripts will be added automatically in the next step.

### 4\. Add and Seal Scripts

For security, the bot will only execute scripts that you have previously "sealed". The process is now automated:

1.  **Add your scripts**: Place your `.sh` or `.py` files into the appropriate folders within the `scripts/` directory.

2.  **Run the sealing script**:

    ```bash
    python seal_scripts.py
    ```

    This command will do two things:

      - **Discover** the new scripts you've added and automatically register them in `configbot.json`.
      - **Calculate and save** the `sha256` hash for all scripts (new and modified ones).

    **You must repeat this step every time you add or modify a script.**

### 5\. Configure Languages (Localization)

If you have added or modified translations in the `.po` files inside the `locales` directory:

```bash
# Compile the language files
pybabel compile -d locales
```

### 6\. Start the Bot

```bash
python bot_interactivo.py
```

Your bot is now running\! You can interact with it on Telegram. To keep it running permanently, consider using `systemd` or `screen`.

-----

## 🔐 Security Considerations

  - **Least Privilege**: Run the bot as a non-root system user with only the permissions it strictly needs.
  - **`sudo` Permissions**: If some commands require `sudo` (like service management), configure `sudoers` to allow the bot's user to run *only* those specific commands without a password.
  - **Secrets Path**: Ensure the `.env` file is in a secure location with read permissions only for the bot's user.
  - **Script Sealing**: Do not underestimate the importance of sealing. It is your primary defense against the execution of unauthorized code if someone gains access to the scripts folder.

-----

## License

This project is licensed under the MIT License.

```
```
