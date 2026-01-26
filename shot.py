# %%
import matplotlib.pyplot as plt  # type: ignore
import matplotlib.font_manager as fm  # type: ignore
from mplsoccer.pitch import VerticalPitch  # type: ignore
import json
import pandas as pd
import requests
import os
from sentence_transformers import SentenceTransformer, util  # type: ignore
import jellyfish  # type: ignore

# %%

with open("players/players_data.json", encoding="utf-8") as p:
    loaded = json.load(p)


def get_player_understat_data(player_id):
    base_url = "https://understat.com"
    player_url = f"{base_url}/getPlayerData/{player_id}"
    try:
        with requests.Session() as session:
            session.headers.update(
                {"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest"}
            )
            r = session.get(player_url)
            if r.status_code == 200:
                return r.json()
    except Exception:
        return None
    return None


def check_if_team_in_league(league_name, season, team_name):
    url = f"https://understat.com/getLeagueData/{league_name}/{season}"
    try:
        with requests.Session() as session:
            session.headers.update(
                {"User-Agent": "Mozilla/5.0", "X-Requested-With": "XMLHttpRequest"}
            )
            r = session.get(url)
            if r.status_code == 200:
                data = r.json()
                main_data = data.get("dates", data.get("date", []))
                for match in main_data:
                    home_team = match.get("h", {}).get("title")
                    away_team = match.get("a", {}).get("title")
                    if home_team == team_name or away_team == team_name:
                        return True
    except Exception:
        return False
    return False


players_data = pd.DataFrame(loaded)
players_data["name"] = players_data["name"].str.lower()
replace_dict = {"Serie A": "Serie_A", "La liga": "La_Liga", "Ligue 1": "Ligue_1"}
players_data["league1"] = players_data["league"].replace(replace_dict)

# %%
df4 = players_data["name"].dropna().astype(str).tolist()
df4 = [name.lower() for name in df4]

model = SentenceTransformer("all-MiniLM-L6-v2")


def matching(input1, df4):
    input_embedding = model.encode(input1)
    df4_embeddings = model.encode(df4)

    similarities = util.cos_sim(input_embedding, df4_embeddings)

    best_match_index = similarities.argmax().item()
    best_match = df4[best_match_index]

    if similarities.max() < 0.8:
        for name in df4:
            input_parts = input1.split()
            name_parts = name.split()

            if input_parts and name_parts:
                input_first_part = input_parts[0]
                name_first_part = name_parts[0]

                if jellyfish.metaphone(input_first_part) == jellyfish.metaphone(
                    name_first_part
                ):
                    return name

    return best_match


# %%
input1 = input("Which player do you want to look at: ")
season = input(
    "For which season (please enter the inital year for any season, for e.g. if you want to see for 2024/25, enter 2024): "
)
input1 = input1.lower()
closest = matching(input1, df4)

if closest:
    new_df = players_data[players_data["name"] == closest]
else:
    print("It is either a typo or no such player exists")

# %%
player_id = new_df.iloc[0, 0]
player_id = str(player_id)
league = new_df.iloc[0, 3]
league_name = new_df.iloc[0, 2]

# %%
player_json_data = get_player_understat_data(player_id)

if not player_json_data:
    print("Error: Could not retrieve data from Understat.")
    exit()

# Get Shots
shots_data = player_json_data["shots"]
df = pd.DataFrame(shots_data)
df = df[df["season"] == season]
player_name = input1  # Or retrieve specific name from json if needed

# --- CALCULATE PER 90 STATS ---
season_groups = player_json_data.get("groups", {}).get("season", [])
current_stats = [item for item in season_groups if str(item["season"]) == str(season)]

if current_stats:
    total_time = sum(float(item["time"]) for item in current_stats)
    total_xg_season = sum(float(item["xG"]) for item in current_stats)
    total_xa_season = sum(float(item["xA"]) for item in current_stats)
    total_shots_season = sum(int(item["shots"]) for item in current_stats)
    total_npxg_season = sum(float(item["npxG"]) for item in current_stats)
else:
    total_time = 0
    total_xg_season = 0
    total_xa_season = 0
    total_shots_season = 0
    total_npxg_season = 0

if total_time > 0:
    xg_p90 = total_xg_season / (total_time / 90)
    shots_p90 = total_shots_season / (total_time / 90)
    npxg_p90 = total_npxg_season / (total_time / 90)
    xgi_p90 = (total_xg_season + total_xa_season) / (total_time / 90)
else:
    xg_p90 = shots_p90 = npxg_p90 = xgi_p90 = 0

# --- DETERMINE TEAM/LEAGUE NAMES ---
unique_teams = list(set(item["team"] for item in current_stats))
leagues_to_check = ["EPL", "La_liga", "Bundesliga", "Serie_A", "Ligue_1", "RFPL"]
final_team_strings = []

print("Verifying leagues for team names...")
for team in unique_teams:
    found_league = None
    for lg in leagues_to_check:
        if check_if_team_in_league(lg, season, team):
            found_league = lg
            break

    if found_league:
        clean_league = found_league.replace("_", " ")
        final_team_strings.append(f"{team} ({clean_league})")
    else:
        final_team_strings.append(f"{team} (Unknown)")

teams_title_str = " + ".join(final_team_strings)

# %%
df["X"] = pd.to_numeric(df["X"])
df["Y"] = pd.to_numeric(df["Y"])
df["xG"] = pd.to_numeric(df["xG"])

df["X"] = df["X"] * 100
df["Y"] = df["Y"] * 100

# %%
number_of_shots = df.shape[0]
number_of_goals = df[df["result"] == "Goal"].shape[0]
number_of_xg = df["xG"].sum()
xg_per_shot = number_of_xg / float(number_of_shots)

# %%
background_color = "#484e48"
background_color2 = "#2c932f"

font_path = "...\lato\Lato-Regular.ttf"
font_props = fm.FontProperties(fname=font_path)

# %%
fig = plt.figure(figsize=(9, 13))
fig.patch.set_facecolor(background_color)

ax1 = fig.add_axes([0, 0.7, 1, 0.2])
for spine in ax1.spines.values():
    spine.set_visible(False)
ax1.set_xticks([])
ax1.set_yticks([])
ax1.set_facecolor(background_color)
ax1.set_xlim(0, 1)
ax1.set_ylim(0, 1)

ax1.text(
    x=0.5,
    y=0.85,
    s=player_name,
    fontsize=25,
    fontproperties=font_props,
    fontweight="bold",
    color="white",
    ha="center",
)

ax1.text(
    x=0.5,
    y=0.71,
    s=f"Shot Map at {teams_title_str} for the {season[2:4]}/{int(season[2:4]) + 1} Season",
    fontsize=13,
    fontproperties=font_props,
    fontweight="bold",
    color="white",
    ha="center",
)

ax1.text(
    x=0.27,
    y=0.5,
    s="Low Quality Chance",
    fontsize=12,
    fontproperties=font_props,
    fontweight="bold",
    color="white",
    ha="center",
)

ax1.scatter(
    x=0.37,
    y=0.53,
    s=100,
    color=background_color,
    edgecolor="white",
    linewidth=0.8,
)

ax1.scatter(
    x=0.42,
    y=0.53,
    s=200,
    color=background_color,
    edgecolor="white",
    linewidth=0.8,
)

ax1.scatter(
    x=0.48,
    y=0.53,
    s=300,
    color=background_color,
    edgecolor="white",
    linewidth=0.8,
)

ax1.scatter(
    x=0.54,
    y=0.53,
    s=400,
    color=background_color,
    edgecolor="white",
    linewidth=0.8,
)

ax1.scatter(
    x=0.61,
    y=0.53,
    s=500,
    color=background_color,
    edgecolor="white",
    linewidth=0.8,
)

ax1.text(
    x=0.723,
    y=0.5,
    s="High Quality Chance",
    fontsize=12,
    fontproperties=font_props,
    fontweight="bold",
    color="white",
    ha="center",
)

ax1.text(
    x=0.096,
    y=0.286,
    s="- Shot Saved",
    fontsize=10,
    fontproperties=font_props,
    color="white",
)

ax1.scatter(
    x=0.08,
    y=0.3,
    s=150,
    color="yellow",
    edgecolor="white",
    linewidth=0.8,
    alpha=0.7,
)

ax1.text(
    x=0.216,
    y=0.286,
    s="- Blocked/Off Target",
    fontsize=10,
    fontproperties=font_props,
    color="white",
)

ax1.scatter(
    x=0.2,
    y=0.3,
    s=150,
    color=background_color,
    edgecolor="white",
    linewidth=0.8,
    alpha=0.7,
)

ax1.text(
    x=0.396,
    y=0.286,
    s="- Goal",
    fontsize=11,
    fontproperties=font_props,
    color="white",
)

ax1.scatter(
    x=0.38,
    y=0.3,
    s=150,
    color="red",
    edgecolor="white",
    linewidth=0.8,
    alpha=0.7,
)

ax1.text(
    x=0.486,
    y=0.286,
    s="- Penalty Scored",
    fontsize=11,
    fontproperties=font_props,
    color="white",
)

ax1.scatter(
    x=0.47,
    y=0.3,
    s=150,
    color="blue",
    marker="s",
    edgecolor="white",
    linewidth=0.8,
    alpha=0.7,
)

ax1.text(
    x=0.646,
    y=0.286,
    s="- Penalty Missed",
    fontsize=11,
    fontproperties=font_props,
    color="white",
)

ax1.scatter(
    x=0.63,
    y=0.3,
    s=150,
    color="violet",
    marker="s",
    edgecolor="white",
    linewidth=0.8,
    alpha=0.7,
)

ax1.text(
    x=0.806,
    y=0.286,
    s="- Freekick Scored",
    fontsize=11,
    fontproperties=font_props,
    color="white",
)

ax1.scatter(
    x=0.79,
    y=0.3,
    s=150,
    color="turquoise",
    marker="^",
    edgecolor="white",
    linewidth=0.8,
    alpha=0.7,
)

ax1.text(
    x=0.83,
    y=-0.1,
    s="xG per 90",
    fontsize=20,
    fontproperties=font_props,
    fontweight="bold",
    color="white",
    ha="left",
)

ax1.text(
    x=0.88,
    y=-0.23,
    s=f"{xg_p90:.2f}",
    fontsize=18,
    fontproperties=font_props,
    fontweight="bold",
    color="white",
    ha="left",
)

ax1.text(
    x=0.82,
    y=-0.51,
    s="Shots per 90",
    fontsize=20,
    fontproperties=font_props,
    fontweight="bold",
    color="white",
    ha="left",
)

ax1.text(
    x=0.88,
    y=-0.63,
    s=f"{shots_p90:.2f}",
    fontsize=18,
    fontproperties=font_props,
    fontweight="bold",
    color="white",
    ha="left",
)

ax1.text(
    x=0.82,
    y=-0.9,
    s="npxG per 90",
    fontsize=20,
    fontproperties=font_props,
    fontweight="bold",
    color="white",
    ha="left",
)

ax1.text(
    x=0.88,
    y=-1.03,
    s=f"{npxg_p90:.2f}",
    fontsize=18,
    fontproperties=font_props,
    fontweight="bold",
    color="white",
    ha="left",
)

ax1.text(
    x=0.83,
    y=-1.3,
    s="xGI per 90",
    fontsize=20,
    fontproperties=font_props,
    fontweight="bold",
    color="white",
    ha="left",
)

ax1.text(
    x=0.88,
    y=-1.43,
    s=f"{xgi_p90:.2f}",
    fontsize=18,
    fontproperties=font_props,
    fontweight="bold",
    color="white",
    ha="left",
)


ax2 = fig.add_axes([0.05, 0.3, 0.72, 0.45])
for spine in ax2.spines.values():
    spine.set_visible(False)
ax2.set_xticks([])
ax2.set_yticks([])
ax2.set_facecolor(background_color2)

pitch = VerticalPitch(
    pitch_type="opta",
    half=True,
    pitch_color=background_color2,
    pad_bottom=0.5,
    line_color="white",
    linewidth=0.75,
    axis=True,
    label=True,
)

pitch.draw(ax=ax2)

for x in df.to_dict(orient="records"):
    pitch.scatter(
        x["X"],
        x["Y"],
        s=400 * x["xG"],
        color=(
            "blue"
            if x["result"] == "Goal" and x["situation"] == "Penalty"
            else "violet"
            if x["result"] != "Goal" and x["situation"] == "Penalty"
            else "turquoise"
            if x["result"] == "Goal" and x["situation"] == "Freekick"
            else "yellow"
            if x["result"] == "SavedShot"
            else "red"
            if x["result"] == "Goal"
            else background_color2
        ),
        marker=(
            "s"
            if x["situation"] == "Penalty"
            else "^"
            if x["situation"] == "Freekick"
            else "o"
        ),
        ax=ax2,
        alpha=0.6,
        linewidth=0.8,
        edgecolor="white",
    )

ax3 = fig.add_axes([0, 0.2, 1, 0.05])
for spine in ax3.spines.values():
    spine.set_visible(False)
ax3.set_xticks([])
ax3.set_yticks([])
ax3.set_facecolor(background_color)

ax3.text(
    x=0.06,
    y=1.8,
    s="Total Shots",
    fontsize=20,
    fontproperties=font_props,
    fontweight="bold",
    color="white",
    ha="left",
)

ax3.text(
    x=0.12,
    y=1.4,
    s=f"{number_of_shots}",
    fontsize=18,
    fontproperties=font_props,
    fontweight="bold",
    color="white",
    ha="left",
)

ax3.text(
    x=0.25,
    y=1.8,
    s="Total Goals",
    fontsize=20,
    fontproperties=font_props,
    fontweight="bold",
    color="white",
    ha="left",
)

ax3.text(
    x=0.32,
    y=1.4,
    s=f"{number_of_goals}",
    fontsize=18,
    fontproperties=font_props,
    fontweight="bold",
    color="white",
    ha="left",
)

ax3.text(
    x=0.44,
    y=1.8,
    s="Total xG",
    fontsize=20,
    fontproperties=font_props,
    fontweight="bold",
    color="white",
    ha="left",
)

ax3.text(
    x=0.48,
    y=1.4,
    s=f"{number_of_xg:.2f}",
    fontsize=18,
    fontproperties=font_props,
    fontweight="bold",
    color="white",
    ha="left",
)

ax3.text(
    x=0.6,
    y=1.8,
    s="xG per Shot",
    fontsize=20,
    fontproperties=font_props,
    fontweight="bold",
    color="white",
    ha="left",
)

ax3.text(
    x=0.66,
    y=1.4,
    s=f"{xg_per_shot:.2f}",
    fontsize=18,
    fontproperties=font_props,
    fontweight="bold",
    color="white",
    ha="left",
)

ax3.text(
    x=0.21,
    y=0.05,
    s="Viz by @BetterThanMario | Github: github.com/AnayShukla | Data: understat.com | EV Data: fplreview.com",
    fontsize=10,
    color="white",
    alpha=0.7,
)

# %%
folder_path = "results"
if not os.path.exists(folder_path):
    os.makedirs(folder_path)

fig.savefig(f"{folder_path}/{player_name}_{season}.png", bbox_inches="tight", dpi=300)
plt.close(fig)
