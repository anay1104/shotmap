## Shotmap
GitHub Repository for the Website: [shotmapgen](https://shotmap.streamlit.app) 

Generates a shot map visualization of a player in the top 5 leagues (PL, La Liga, Serie A, Bundesliga, Ligue 1) and RFPL, all this data sourced from [Understat](https://understat.com).

## Tutorial
1. Download the zip file and extract its contents or run the following in your terminal:
```
git clone https://github.com/AnayShukla/shotmap.git
```
2. Set the directory to the path where you have cloned the repository, (most of the times just run this):
```
cd shotmap
```
3. To install all the required packages, run:
```
pip install -r requirements.txt
```
4. To generate the output, run:
```
python shot.py
```

## Generating Output
1. Enter the name of the player whose shot map you wish to see. You can also enter discrete names such as **salah** to get it for **Mohammed Salah**, but avoid doing so for players with common names or vague spellings (basically specificity is preferred :) )
2. Enter the initial year of the season of your choice. For e.g. if you wish to see it for the 2024/25 season, enter 2024.
3. Check `shotmap/results` to find the exported image.

## Example
Entering Mohamed Salah and 2024 would yield you an image like this:

![Salah_2024](https://github.com/user-attachments/assets/104fd335-a4a7-426b-8919-5c410fa076ed)


## Note
Reminder that this is still a work in progress, will be making fixes with a few issues and also try to introduce new updates as well. Works perfectly for all players for the current season, however for players who played in a different league 
in any of the previous seasons will not yield accurate outputs, hoping to fix it soon!

## Socials
You can also reach out to me on:
- [Twitter](https://x.com/BetterThanMario)
- [BlueSky](https://bsky.app/profile/luigi1104.bsky.social)

