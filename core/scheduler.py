"""
FaucetPlay Bot - Scheduler Module
Handles scheduled bot execution
"""

import schedule
import time
import threading
from typing import Callable, List, Dict
from datetime import datetime, time as dt_time


class BotScheduler:
    """Manages scheduled bot runs"""
    
    def __init__(self, bot_start_callback: Callable, bot_stop_callback: Callable):
        self.bot_start = bot_start_callback
        self.bot_stop = bot_stop_callback
        self.running = False
        self.thread = None
        self.schedules = []
    
    def add_schedule(self, schedule_config: Dict):
        """
        Add a schedule configuration
        
        schedule_config = {
            'enabled': True,
            'days': ['monday', 'tuesday', 'wednesday', 'thursday', 'friday'],
            'start_time': '09:00',
            'end_time': '17:00',
            'name': 'Weekday Trading'
        }
        """
        self.schedules.append(schedule_config)
    
    def remove_schedule(self, index: int):
        """Remove a schedule by index"""
        if 0 <= index < len(self.schedules):
            self.schedules.pop(index)
    
    def clear_schedules(self):
        """Clear all schedules"""
        self.schedules.clear()
        schedule.clear()
    
    def _setup_schedules(self):
        """Setup schedule jobs"""
        schedule.clear()
        
        for sched in self.schedules:
            if not sched.get('enabled', True):
                continue
            
            days = sched.get('days', [])
            start_time = sched.get('start_time', '00:00')
            end_time = sched.get('end_time', '23:59')
            
            # Schedule start time
            for day in days:
                day_method = getattr(schedule.every(), day.lower(), None)
                if day_method:
                    day_method.at(start_time).do(self._scheduled_start)
            
            # Schedule stop time
            for day in days:
                day_method = getattr(schedule.every(), day.lower(), None)
                if day_method:
                    day_method.at(end_time).do(self._scheduled_stop)
    
    def _scheduled_start(self):
        """Called when scheduled start time is reached"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Scheduled bot start")
        self.bot_start()
    
    def _scheduled_stop(self):
        """Called when scheduled stop time is reached"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Scheduled bot stop")
        self.bot_stop()
    
    def start(self):
        """Start the scheduler"""
        if self.running:
            return
        
        self._setup_schedules()
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        print("Scheduler started")
    
    def stop(self):
        """Stop the scheduler"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        print("Scheduler stopped")
    
    def _run(self):
        """Run the scheduler loop"""
        while self.running:
            schedule.run_pending()
            time.sleep(1)
    
    def get_next_run(self) -> str:
        """Get next scheduled run time"""
        next_run = schedule.next_run()
        if next_run:
            return next_run.strftime('%Y-%m-%d %H:%M:%S')
        return "No schedules configured"
    
    def get_schedules(self) -> List[Dict]:
        """Get all schedule configurations"""
        return self.schedules.copy()
