# WNBA Prediction Engine - Setup Instructions

## Quick Setup (One Script)

To completely reproduce the WNBA prediction engine environment on a new Windows computer:

### Option 1: Batch Script (Recommended)
1. Download `setup_complete_pipeline.bat` to your desired directory
2. Double-click the file or run it from Command Prompt
3. The script will automatically:
   - Clone the repository from GitHub
   - Create a virtual environment
   - Install all dependencies
   - Run all data acquisition scripts
   - Run all data processing scripts
   - Validate the data

### Option 2: PowerShell Script
1. Download `setup_complete_pipeline.ps1` to your desired directory
2. Right-click the file and select "Run with PowerShell" or run it from PowerShell
3. Same functionality as the batch script but with colored output

## Prerequisites

Before running the setup scripts, ensure you have:
- **Python 3.8+** installed and in your PATH
- **Git** installed and in your PATH

## What the Scripts Do

The setup scripts will:

1. **Clone Repository**: Download the complete project from GitHub
2. **Create Virtual Environment**: Set up an isolated Python environment
3. **Install Dependencies**: Install all required packages from `requirements.txt`
4. **Create Directories**: Set up data, models, and plots folders
5. **Fetch Data**: Download all WNBA data (boxscores, play-by-play, team gamelogs)
6. **Validate Data**: Check data completeness and coverage
7. **Process Data**: Add miscellaneous stats and build possession-based features
8. **Final Validation**: Verify on-court player tracking

## Expected Output

After running the script, you'll have:
- `data/raw/` - Raw boxscores, play-by-play, and team gamelogs
- `data/processed/` - Processed data with additional stats
- `data/features/` - Possession-based player features
- `models/` - Directory for trained models (empty initially)
- `plots/` - Directory for generated plots (empty initially)

## Troubleshooting

### Common Issues:
- **Python not found**: Install Python 3.8+ and add to PATH
- **Git not found**: Install Git and add to PATH
- **Permission errors**: Run as administrator if needed
- **Network issues**: Check internet connection for GitHub and package downloads

### Manual Steps (if script fails):
1. Clone repository: `git clone https://github.com/gallagjj/wnba-prediction-engine.git`
2. Create virtual environment: `python -m venv venv`
3. Activate environment: `venv\Scripts\activate.bat` (or `venv\Scripts\Activate.ps1`)
4. Install dependencies: `pip install -r requirements.txt`
5. Run scripts manually in order (see script order in the setup files)

## After Setup

Once the script completes successfully:
- Your environment is ready for modeling and analysis
- All data is downloaded and processed
- You can start working on the next phase of the project

## Future Use

To activate the environment in the future:
```bash
cd wnba-prediction-engine
venv\Scripts\activate.bat  # or venv\Scripts\Activate.ps1
```

To run individual scripts:
```bash
python scripts\01_acquisition\script_name.py
python scripts\02_processing\script_name.py
``` 