import os
import subprocess
import sys

def run_script(module_name):
    print(f"\n{'='*50}\nRunning {module_name}...\n{'='*50}")
    result = subprocess.run([sys.executable, "-m", module_name], cwd=os.path.dirname(os.path.abspath(__file__)))
    if result.returncode != 0:
        print(f"Error running {module_name}")
        return False
    return True

if __name__ == "__main__":
    modules = [
        "src.db_schema",
        "src.pipeline_ticker_master",
        "src.pipeline_daily_market",
        "src.pipeline_earnings",
        "src.pipeline_relationships",
        "src.pipeline_secondary"
    ]
    
    for module in modules:
        if not run_script(module):
            sys.exit(1)
            
    print("\nDatabase build completed successfully!")
