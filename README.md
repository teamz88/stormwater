# Stormwater Reports Scraper

A Python automation tool that scrapes stormwater compliance reports from StormwaterPro platform, downloads PDF reports, and integrates with n8n workflows for further processing.

## Features

- **Automated Web Scraping**: Uses Playwright to navigate and scrape reports from StormwaterPro platform
- **Database Integration**: SQLite database to track reports and prevent duplicate downloads
- **PDF Download Management**: Automatically downloads new report PDFs with organized naming
- **Notification System**: Real-time notifications via ntfy for success/error alerts
- **Webhook Integration**: Sends data to n8n workflows for further automation
- **Flexible Date Filtering**: Can target specific dates or automatically use the latest reports
- **Cron Job Ready**: Includes scripts for automated daily execution

## Prerequisites

- Python 3.7+
- Chrome/Chromium browser (for Playwright)
- Access to StormwaterPro platform with valid credentials

## Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd stormwater
   ```

2. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Playwright browsers**:
   ```bash
   playwright install chromium
   ```

4. **Set up environment variables**:
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` file with your credentials:
   ```env
   STORMWATER_USERNAME="your_username"
   STORMWATER_PASSWORD="your_password"
   STORMWATER_LOGIN_URL="https://yourcompany.compli.cloud/auth/login"
   STORMWATER_REPORT_URL="https://yourcompany.compli.cloud/analytics/reports/created-by-period"
   N8N_WEBHOOK_URL="https://app.n8n.cloud/webhook/your-webhook-id"
   N8N_ERROR_WEBHOOK_URL="https://app.n8n.cloud/webhook/your-error-webhook-id"
   ```

## Usage

### Manual Execution

**Run with latest reports**:
```bash
python app.py
```

**Run with specific date**:
```bash
python app.py --date 2024-01-15
```

### Automated Execution

**Set up daily cron job**:
```bash
# Make scripts executable
chmod +x run_app.sh setup_cron.sh

# Run the setup script
./setup_cron.sh
```

This will configure a daily cron job that runs the scraper automatically.

## Project Structure

```
stormwater/
├── app.py              # Main application script
├── database.py         # SQLite database management
├── requirements.txt    # Python dependencies
├── .env.example       # Environment variables template
├── .env               # Your environment variables (create from .env.example)
├── run_app.sh         # Shell script for automated execution
├── setup_cron.sh      # Cron job setup script
├── reports.json       # Latest scraped reports data
├── reports.db         # SQLite database file
└── logs/              # Application logs directory
```

## How It Works

1. **Authentication**: Logs into StormwaterPro platform using provided credentials
2. **Report Discovery**: Navigates to reports page and scrapes available reports
3. **Date Filtering**: Filters reports by target date (latest or specified)
4. **Database Check**: Compares with existing database to identify new reports
5. **PDF Download**: Downloads PDF files for new reports only
6. **Data Processing**: Saves report metadata to JSON and SQLite database
7. **Webhook Integration**: Sends new reports data to n8n webhook for processing
8. **Notifications**: Sends success/error notifications via ntfy

## Database Schema

The SQLite database stores report metadata with the following structure:

- `rd_id` (PRIMARY KEY): Report definition ID
- `site`: Site name
- `program`: Program type
- `report_type`: Type of report
- `date`: Report date
- `pdf_downloaded`: Boolean flag for PDF download status
- Additional metadata fields for complete report information

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `STORMWATER_USERNAME` | Platform login username | Yes |
| `STORMWATER_PASSWORD` | Platform login password | Yes |
| `STORMWATER_LOGIN_URL` | Login page URL | Yes |
| `STORMWATER_REPORT_URL` | Reports page URL | Yes |
| `N8N_WEBHOOK_URL` | Webhook for successful data | No |
| `N8N_ERROR_WEBHOOK_URL` | Webhook for error notifications | No |

### Notification Setup

The application uses ntfy.sh for notifications. Configure your ntfy server:
- Server: `https://ntfy.hvacvoice.com`
- Topic: `stormwater`
- Icon: StormwaterPro favicon

## Logging

Logs are stored in the `logs/` directory with timestamps. Each execution creates a new log file for tracking:
- Application progress
- Error messages
- Download status
- Database operations

## Error Handling

The application includes comprehensive error handling:
- **Authentication failures**: Automatic retry and notification
- **Network issues**: Timeout handling and retries
- **Missing elements**: Graceful degradation
- **Database errors**: Transaction rollback and logging
- **Webhook failures**: Error notifications without stopping execution

## Troubleshooting

### Common Issues

1. **Login failures**:
   - Verify credentials in `.env` file
   - Check if login URL is correct
   - Ensure account is not locked

2. **Download issues**:
   - Check Downloads directory permissions
   - Verify report URLs are accessible
   - Check for browser/Playwright issues

3. **Database errors**:
   - Ensure write permissions for `reports.db`
   - Check disk space availability

4. **Cron job not running**:
   - Verify cron service is running
   - Check cron job syntax with `crontab -l`
   - Review log files in `logs/` directory

### Debug Mode

For debugging, you can modify the Playwright launch options in `app.py`:
```python
browser = p.chromium.launch(
    headless=False,  # Set to False to see browser
    slow_mo=1000     # Add delay between actions
)
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review log files for error details
3. Create an issue in the repository
4. Include relevant log excerpts and configuration details