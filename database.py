import sqlite3
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

class ReportsDatabase:
    def __init__(self, db_path: str = "reports.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize the database and create tables if they don't exist"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create reports table with rd_id as primary key
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS reports (
                        rd_id TEXT PRIMARY KEY,
                        id TEXT,
                        site TEXT NOT NULL,
                        site_url TEXT,
                        program TEXT,
                        report_type TEXT,
                        report_definition TEXT,
                        report_definition_url TEXT,
                        site_tags TEXT,
                        publishing_user TEXT,
                        date TEXT NOT NULL,
                        time TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        pdf_downloaded BOOLEAN DEFAULT FALSE
                    )
                """)
                
                # Create index on date for faster queries
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_reports_date ON reports(date)
                """)
                
                # Create index on rd_id for faster lookups
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_reports_rd_id ON reports(rd_id)
                """)
                
                conn.commit()
                logging.info("Database initialized successfully")
                
        except Exception as e:
            logging.error(f"Error initializing database: {e}")
            raise
    
    def insert_report(self, report: Dict[str, Any]) -> bool:
        """Insert a single report into the database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT OR REPLACE INTO reports 
                    (id, site, site_url, program, report_type, report_definition, 
                     report_definition_url, rd_id, site_tags, publishing_user, date, time)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    report['id'],
                    report['site'],
                    report['site_url'],
                    report['program'],
                    report['report_type'],
                    report['report_definition'],
                    report['report_definition_url'],
                    report['rd_id'],
                    report['site_tags'],
                    report['publishing_user'],
                    report['date'],
                    report['time']
                ))
                
                conn.commit()
                return True
                
        except Exception as e:
            logging.error(f"Error inserting report {report.get('id', 'unknown')}: {e}")
            return False
    
    def insert_reports_batch(self, reports: List[Dict[str, Any]]) -> int:
        """Insert multiple reports into the database"""
        inserted_count = 0
        failed_count = 0
        
        logging.info(f"Starting batch insert of {len(reports)} reports")
        
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                for i, report in enumerate(reports, 1):
                    try:
                        # Validate required fields
                        if not report.get('rd_id'):
                            logging.error(f"Report {i}: Missing required 'rd_id' field")
                            failed_count += 1
                            continue
                            
                        if not report.get('site'):
                            logging.error(f"Report {i} (RD_ID: {report.get('rd_id')}): Missing required 'site' field")
                            failed_count += 1
                            continue
                            
                        if not report.get('date'):
                            logging.error(f"Report {i} (RD_ID: {report.get('rd_id')}): Missing required 'date' field")
                            failed_count += 1
                            continue
                        
                        cursor.execute("""
                            INSERT OR REPLACE INTO reports 
                            (rd_id, id, site, site_url, program, report_type, report_definition, 
                             report_definition_url, site_tags, publishing_user, date, time)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            report.get('rd_id', ''),
                            report['id'],
                            report['site'],
                            report.get('site_url', ''),
                            report.get('program', ''),
                            report.get('report_type', ''),
                            report.get('report_definition', ''),
                            report.get('report_definition_url', ''),
                            report.get('site_tags', ''),
                            report.get('publishing_user', ''),
                            report['date'],
                            report.get('time', '')
                        ))
                        inserted_count += 1
                        logging.debug(f"Successfully inserted report {i} (RD_ID: {report.get('rd_id')})")
                        
                    except Exception as e:
                        failed_count += 1
                        logging.error(f"Error inserting report {i} (RD_ID: {report.get('rd_id', 'unknown')}): {e}")
                        logging.error(f"Report data: {report}")
                
                conn.commit()
                logging.info(f"Batch insert completed: {inserted_count} successful, {failed_count} failed")
                
        except Exception as e:
            logging.error(f"Error in batch insert: {e}")
        
        return inserted_count
    
    def report_exists(self, rd_id: str) -> bool:
        """Check if a report exists in the database by rd_id"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1 FROM reports WHERE rd_id = ?", (rd_id,))
                return cursor.fetchone() is not None
                
        except Exception as e:
            logging.error(f"Error checking if report exists: {e}")
            return False
    
    def get_new_reports(self, reports: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter reports to return only those not in the database"""
        new_reports = []
        
        for report in reports:
            if report.get('rd_id') and not self.report_exists(report['rd_id']):
                new_reports.append(report)
        
        logging.info(f"Found {len(new_reports)} new reports out of {len(reports)} total")
        return new_reports
    
    def mark_pdf_downloaded(self, rd_id: str) -> bool:
        """Mark a report as having its PDF downloaded by rd_id"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE reports SET pdf_downloaded = TRUE WHERE rd_id = ?", 
                    (rd_id,)
                )
                conn.commit()
                return cursor.rowcount > 0
                
        except Exception as e:
            logging.error(f"Error marking PDF as downloaded for report {rd_id}: {e}")
            return False
    
    def get_reports_by_date(self, date: str) -> List[Dict[str, Any]]:
        """Get all reports for a specific date"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, site, site_url, program, report_type, report_definition,
                           report_definition_url, rd_id, site_tags, publishing_user, date, time
                    FROM reports WHERE date = ?
                    ORDER BY time DESC
                """, (date,))
                
                columns = [desc[0] for desc in cursor.description]
                reports = []
                
                for row in cursor.fetchall():
                    report = dict(zip(columns, row))
                    reports.append(report)
                
                return reports
                
        except Exception as e:
            logging.error(f"Error getting reports by date {date}: {e}")
            return []
    
    def get_all_reports(self) -> List[Dict[str, Any]]:
        """Get all reports from the database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, site, site_url, program, report_type, report_definition,
                           report_definition_url, rd_id, site_tags, publishing_user, date, time
                    FROM reports
                    ORDER BY date DESC, time DESC
                """)
                
                columns = [desc[0] for desc in cursor.description]
                reports = []
                
                for row in cursor.fetchall():
                    report = dict(zip(columns, row))
                    reports.append(report)
                
                return reports
                
        except Exception as e:
            logging.error(f"Error getting all reports: {e}")
            return []
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Total reports count
                cursor.execute("SELECT COUNT(*) FROM reports")
                total_reports = cursor.fetchone()[0]
                
                # Reports by date
                cursor.execute("""
                    SELECT date, COUNT(*) as count 
                    FROM reports 
                    GROUP BY date 
                    ORDER BY date DESC 
                    LIMIT 10
                """)
                reports_by_date = cursor.fetchall()
                
                # PDFs downloaded count
                cursor.execute("SELECT COUNT(*) FROM reports WHERE pdf_downloaded = TRUE")
                pdfs_downloaded = cursor.fetchone()[0]
                
                return {
                    'total_reports': total_reports,
                    'pdfs_downloaded': pdfs_downloaded,
                    'recent_dates': reports_by_date
                }
                
        except Exception as e:
            logging.error(f"Error getting database stats: {e}")
            return {}