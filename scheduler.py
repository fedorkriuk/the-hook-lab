from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.base import JobLookupError
import logging
import atexit
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable, List
import os
# Environment variables are loaded via config.py

class TrendBotScheduler:
    def __init__(self, config=None):
        self.logger = logging.getLogger(__name__)
        self.config = config
        self.scheduler = BackgroundScheduler()
        self.jobs = {}
        self.is_running = False
        
        # Default intervals (can be overridden via environment variables)
        self.collection_interval_hours = int(os.getenv('COLLECTION_INTERVAL_HOURS', 2))
        self.analysis_interval_hours = int(os.getenv('ANALYSIS_INTERVAL_HOURS', 12))
        self.publishing_interval_hours = int(os.getenv('PUBLISHING_INTERVAL_HOURS', 8))
        self.cleanup_interval_days = int(os.getenv('CLEANUP_INTERVAL_DAYS', 1))
        
        # Publish times (in 24-hour format)
        self.publish_times = [
            os.getenv('PUBLISH_TIME_1', '09:00'),  # 9 AM
            os.getenv('PUBLISH_TIME_2', '15:00'),  # 3 PM
            os.getenv('PUBLISH_TIME_3', '21:00')   # 9 PM
        ]
        
        # Register cleanup on exit
        atexit.register(self.shutdown)
    
    def start(self):
        """Start the scheduler."""
        try:
            if not self.is_running:
                self.scheduler.start()
                self.is_running = True
                self.logger.info("TrendBot scheduler started successfully")
            else:
                self.logger.warning("Scheduler is already running")
        except Exception as e:
            self.logger.error(f"Error starting scheduler: {e}")
            raise
    
    def shutdown(self):
        """Shutdown the scheduler gracefully."""
        try:
            if self.is_running:
                self.scheduler.shutdown(wait=True)
                self.is_running = False
                self.logger.info("TrendBot scheduler shut down successfully")
        except Exception as e:
            self.logger.error(f"Error shutting down scheduler: {e}")
    
    def add_data_collection_job(self, collector_func: Callable, 
                              interval_hours: Optional[int] = None) -> str:
        """Add a recurring data collection job."""
        try:
            interval = interval_hours or self.collection_interval_hours
            job_id = "data_collection"
            
            # Remove existing job if it exists
            self._remove_job_if_exists(job_id)
            
            # Add new job
            job = self.scheduler.add_job(
                func=self._safe_job_wrapper(collector_func, "Data Collection"),
                trigger=IntervalTrigger(hours=interval),
                id=job_id,
                name="Data Collection Job",
                misfire_grace_time=300,  # 5 minutes grace time
                coalesce=True,  # Combine missed jobs
                max_instances=1  # Only one instance at a time
            )
            
            self.jobs[job_id] = job
            self.logger.info(f"Data collection job scheduled every {interval} hours")
            return job_id
            
        except Exception as e:
            self.logger.error(f"Error adding data collection job: {e}")
            raise
    
    def add_analysis_job(self, analysis_func: Callable,
                        interval_hours: Optional[int] = None) -> str:
        """Add a recurring analysis job."""
        try:
            interval = interval_hours or self.analysis_interval_hours
            job_id = "trend_analysis"
            
            # Remove existing job if it exists
            self._remove_job_if_exists(job_id)
            
            # Add new job
            job = self.scheduler.add_job(
                func=self._safe_job_wrapper(analysis_func, "Trend Analysis"),
                trigger=IntervalTrigger(hours=interval),
                id=job_id,
                name="Trend Analysis Job",
                misfire_grace_time=600,  # 10 minutes grace time
                coalesce=True,
                max_instances=1
            )
            
            self.jobs[job_id] = job
            self.logger.info(f"Trend analysis job scheduled every {interval} hours")
            return job_id
            
        except Exception as e:
            self.logger.error(f"Error adding analysis job: {e}")
            raise
    
    def add_publishing_jobs(self, publisher_func: Callable) -> List[str]:
        """Add scheduled publishing jobs at specific times."""
        try:
            job_ids = []
            
            for i, publish_time in enumerate(self.publish_times):
                job_id = f"publishing_{i+1}"
                
                # Remove existing job if it exists
                self._remove_job_if_exists(job_id)
                
                # Parse time
                try:
                    hour, minute = map(int, publish_time.split(':'))
                except ValueError:
                    self.logger.warning(f"Invalid publish time format: {publish_time}")
                    continue
                
                # Add daily job at specific time
                job = self.scheduler.add_job(
                    func=self._safe_job_wrapper(publisher_func, f"Publishing {i+1}"),
                    trigger=CronTrigger(hour=hour, minute=minute),
                    id=job_id,
                    name=f"Publishing Job {i+1} ({publish_time})",
                    misfire_grace_time=1800,  # 30 minutes grace time
                    coalesce=True,
                    max_instances=1
                )
                
                self.jobs[job_id] = job
                job_ids.append(job_id)
                self.logger.info(f"Publishing job {i+1} scheduled daily at {publish_time}")
            
            return job_ids
            
        except Exception as e:
            self.logger.error(f"Error adding publishing jobs: {e}")
            raise
    
    def add_cleanup_job(self, cleanup_func: Callable,
                       interval_days: Optional[int] = None) -> str:
        """Add a recurring cleanup job."""
        try:
            interval = interval_days or self.cleanup_interval_days
            job_id = "cleanup"
            
            # Remove existing job if it exists
            self._remove_job_if_exists(job_id)
            
            # Add daily cleanup job at 2 AM
            job = self.scheduler.add_job(
                func=self._safe_job_wrapper(cleanup_func, "Cleanup"),
                trigger=CronTrigger(hour=2, minute=0),  # 2 AM daily
                id=job_id,
                name="Cleanup Job",
                misfire_grace_time=3600,  # 1 hour grace time
                coalesce=True,
                max_instances=1
            )
            
            self.jobs[job_id] = job
            self.logger.info("Daily cleanup job scheduled at 2:00 AM")
            return job_id
            
        except Exception as e:
            self.logger.error(f"Error adding cleanup job: {e}")
            raise
    
    def add_visualization_job(self, visualization_func: Callable,
                            interval_hours: int = 6) -> str:
        """Add a recurring visualization generation job."""
        try:
            job_id = "visualization"
            
            # Remove existing job if it exists
            self._remove_job_if_exists(job_id)
            
            # Add visualization job
            job = self.scheduler.add_job(
                func=self._safe_job_wrapper(visualization_func, "Visualization"),
                trigger=IntervalTrigger(hours=interval_hours),
                id=job_id,
                name="Visualization Job",
                misfire_grace_time=600,  # 10 minutes grace time
                coalesce=True,
                max_instances=1
            )
            
            self.jobs[job_id] = job
            self.logger.info(f"Visualization job scheduled every {interval_hours} hours")
            return job_id
            
        except Exception as e:
            self.logger.error(f"Error adding visualization job: {e}")
            raise
    
    def add_one_time_job(self, func: Callable, run_time: datetime, 
                        job_id: str = None, name: str = None) -> str:
        """Add a one-time job to run at a specific time."""
        try:
            if not job_id:
                job_id = f"onetime_{int(run_time.timestamp())}"
            
            if not name:
                name = f"One-time Job ({run_time.strftime('%Y-%m-%d %H:%M:%S')})"
            
            # Remove existing job if it exists
            self._remove_job_if_exists(job_id)
            
            job = self.scheduler.add_job(
                func=self._safe_job_wrapper(func, name),
                trigger='date',
                run_date=run_time,
                id=job_id,
                name=name,
                misfire_grace_time=300,  # 5 minutes grace time
                max_instances=1
            )
            
            self.jobs[job_id] = job
            self.logger.info(f"One-time job '{name}' scheduled for {run_time}")
            return job_id
            
        except Exception as e:
            self.logger.error(f"Error adding one-time job: {e}")
            raise
    
    def remove_job(self, job_id: str) -> bool:
        """Remove a scheduled job."""
        try:
            if job_id in self.jobs:
                self.scheduler.remove_job(job_id)
                del self.jobs[job_id]
                self.logger.info(f"Job '{job_id}' removed successfully")
                return True
            else:
                self.logger.warning(f"Job '{job_id}' not found")
                return False
                
        except JobLookupError:
            self.logger.warning(f"Job '{job_id}' not found in scheduler")
            return False
        except Exception as e:
            self.logger.error(f"Error removing job '{job_id}': {e}")
            return False
    
    def _remove_job_if_exists(self, job_id: str):
        """Helper to remove a job if it exists."""
        try:
            if job_id in self.jobs:
                self.scheduler.remove_job(job_id)
                del self.jobs[job_id]
        except JobLookupError:
            pass  # Job doesn't exist, that's fine
    
    def _safe_job_wrapper(self, func: Callable, job_name: str) -> Callable:
        """Wrap job functions with error handling."""
        def wrapper(*args, **kwargs):
            try:
                self.logger.info(f"Starting {job_name} job")
                start_time = datetime.now()
                
                result = func(*args, **kwargs)
                
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                self.logger.info(f"{job_name} job completed successfully in {duration:.2f} seconds")
                
                return result
                
            except Exception as e:
                self.logger.error(f"Error in {job_name} job: {e}", exc_info=True)
                # Don't re-raise to prevent job from being removed from scheduler
        
        return wrapper
    
    def get_job_status(self) -> Dict[str, Any]:
        """Get status of all scheduled jobs."""
        try:
            status = {
                'scheduler_running': self.is_running,
                'total_jobs': len(self.jobs),
                'jobs': {}
            }
            
            for job_id, job in self.jobs.items():
                job_info = {
                    'id': job.id,
                    'name': job.name,
                    'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
                    'trigger': str(job.trigger),
                    'misfire_grace_time': job.misfire_grace_time,
                    'max_instances': job.max_instances
                }
                status['jobs'][job_id] = job_info
            
            return status
            
        except Exception as e:
            self.logger.error(f"Error getting job status: {e}")
            return {'error': str(e)}
    
    def get_next_runs(self, hours: int = 24) -> List[Dict[str, Any]]:
        """Get upcoming job runs within the next specified hours."""
        try:
            upcoming = []
            end_time = datetime.now() + timedelta(hours=hours)
            
            for job_id, job in self.jobs.items():
                if job.next_run_time and job.next_run_time <= end_time:
                    upcoming.append({
                        'job_id': job_id,
                        'job_name': job.name,
                        'next_run': job.next_run_time.isoformat(),
                        'time_until': str(job.next_run_time - datetime.now())
                    })
            
            # Sort by next run time
            upcoming.sort(key=lambda x: x['next_run'])
            return upcoming
            
        except Exception as e:
            self.logger.error(f"Error getting next runs: {e}")
            return []
    
    def pause_job(self, job_id: str) -> bool:
        """Pause a specific job."""
        try:
            if job_id in self.jobs:
                self.scheduler.pause_job(job_id)
                self.logger.info(f"Job '{job_id}' paused")
                return True
            else:
                self.logger.warning(f"Job '{job_id}' not found")
                return False
                
        except Exception as e:
            self.logger.error(f"Error pausing job '{job_id}': {e}")
            return False
    
    def resume_job(self, job_id: str) -> bool:
        """Resume a paused job."""
        try:
            if job_id in self.jobs:
                self.scheduler.resume_job(job_id)
                self.logger.info(f"Job '{job_id}' resumed")
                return True
            else:
                self.logger.warning(f"Job '{job_id}' not found")
                return False
                
        except Exception as e:
            self.logger.error(f"Error resuming job '{job_id}': {e}")
            return False
    
    def reschedule_job(self, job_id: str, **schedule_kwargs) -> bool:
        """Reschedule an existing job with new parameters."""
        try:
            if job_id in self.jobs:
                self.scheduler.reschedule_job(job_id, **schedule_kwargs)
                self.logger.info(f"Job '{job_id}' rescheduled")
                return True
            else:
                self.logger.warning(f"Job '{job_id}' not found")
                return False
                
        except Exception as e:
            self.logger.error(f"Error rescheduling job '{job_id}': {e}")
            return False
    
    def run_job_now(self, job_id: str) -> bool:
        """Manually trigger a job to run immediately."""
        try:
            if job_id in self.jobs:
                job = self.jobs[job_id]
                # Get the job function and run it
                job.func()
                self.logger.info(f"Job '{job_id}' executed manually")
                return True
            else:
                self.logger.warning(f"Job '{job_id}' not found")
                return False
                
        except Exception as e:
            self.logger.error(f"Error running job '{job_id}' manually: {e}")
            return False
    
    def get_job_history(self, job_id: str = None) -> List[Dict[str, Any]]:
        """Get execution history for jobs (if logging is configured appropriately)."""
        # This is a placeholder - real implementation would require
        # integration with a job execution tracking system
        try:
            # For now, return basic info from scheduler
            if job_id and job_id in self.jobs:
                job = self.jobs[job_id]
                return [{
                    'job_id': job_id,
                    'last_run': 'N/A',  # Would need job store with history
                    'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
                    'status': 'scheduled'
                }]
            else:
                # Return all jobs basic info
                history = []
                for jid, job in self.jobs.items():
                    history.append({
                        'job_id': jid,
                        'job_name': job.name,
                        'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
                        'status': 'scheduled'
                    })
                return history
                
        except Exception as e:
            self.logger.error(f"Error getting job history: {e}")
            return []