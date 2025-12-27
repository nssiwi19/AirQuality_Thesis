"""
Script to view AirWatch database contents with beautiful tables
Using 'rich' library for formatting
"""
import sqlite3
import os
import json

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich import box
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("⚠️ Install 'rich' for better display: pip install rich")

# Load station names from stations.json
def load_station_names():
    try:
        with open("stations.json", "r", encoding="utf-8") as f:
            stations = json.load(f)
            return {s['uid']: s['name'] for s in stations}
    except:
        return {}

STATION_NAMES = load_station_names()

def get_station_name(uid):
    """Get station name from UID"""
    return STATION_NAMES.get(uid, f"Unknown ({uid})")

def view_database():
    db_file = "air_quality_asean.db"
    
    if not os.path.exists(db_file):
        print(f"❌ Database file '{db_file}' not found!")
        print("   Run the server first to create the database.")
        return
    
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    
    if RICH_AVAILABLE:
        console = Console()
        
        # Database info panel
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cursor.fetchall()]
        console.print(Panel(f"[bold cyan]Tables:[/] {', '.join(tables)}", title="📊 AirWatch Database"))
        
        # Measurements table
        if 'measurements' in tables:
            cursor.execute("SELECT COUNT(*) FROM measurements")
            count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(DISTINCT station_uid) FROM measurements")
            stations = cursor.fetchone()[0]
            
            cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM measurements")
            min_ts, max_ts = cursor.fetchone()
            
            console.print(f"\n[bold green]📈 Measurements:[/] {count:,} records | {stations} stations")
            console.print(f"   [dim]Date range: {min_ts} → {max_ts}[/]")
            
            # Create beautiful table with STATION NAMES
            table = Table(title="🕐 Latest 15 Measurements", box=box.ROUNDED)
            table.add_column("Station Name", style="cyan", max_width=35)
            table.add_column("AQI", style="bold", justify="center")
            table.add_column("PM2.5", justify="center")
            table.add_column("Timestamp", style="dim")
            
            cursor.execute("""
                SELECT station_uid, aqi, pm25, timestamp 
                FROM measurements 
                ORDER BY timestamp DESC 
                LIMIT 15
            """)
            
            for row in cursor.fetchall():
                uid = row[0]
                aqi = row[1]
                station_name = get_station_name(uid)
                
                # Color based on AQI level
                if aqi <= 50:
                    aqi_style = "[green]"
                elif aqi <= 100:
                    aqi_style = "[yellow]"
                elif aqi <= 150:
                    aqi_style = "[orange1]"
                elif aqi <= 200:
                    aqi_style = "[red]"
                else:
                    aqi_style = "[purple]"
                
                table.add_row(
                    station_name[:35],
                    f"{aqi_style}{aqi}[/]",
                    str(row[2]),
                    str(row[3])[:19]  # Truncate timestamp
                )
            
            console.print(table)
        
        # Alerts table
        if 'alerts' in tables:
            cursor.execute("SELECT COUNT(*) FROM alerts")
            alert_count = cursor.fetchone()[0]
            console.print(f"\n[bold yellow]⚠️ Alerts:[/] {alert_count} records")
    else:
        # Fallback without rich
        print("\n--- Measurements (latest 10) ---")
        cursor.execute("SELECT station_uid, aqi, pm25, timestamp FROM measurements ORDER BY timestamp DESC LIMIT 10")
        for row in cursor.fetchall():
            name = get_station_name(row[0])
            print(f"  {name}: AQI={row[1]}, PM2.5={row[2]}, Time={row[3]}")
    
    conn.close()
    print("\n✅ Done!")

if __name__ == "__main__":
    view_database()
