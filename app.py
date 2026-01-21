import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from mplsoccer import VerticalPitch
import json
import pandas as pd
import understatapi
import numpy as np
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import Select
from selenium.webdriver.chrome.options import Options
import time
from sentence_transformers import SentenceTransformer, util
import jellyfish
from webdriver_manager.chrome import ChromeDriverManager
import torch
from io import BytesIO
import streamlit as st

st.set_page_config(page_title="Shotmapgen", page_icon=":soccer:")


@st.cache_data
def load_data():
    with open("players/players_data.json", encoding="utf-8") as p:
        loaded = json.load(p)
    df = pd.DataFrame(loaded)
    return df


players_data = load_data()
player_names = sorted(players_data["name"].unique().tolist())

available_seasons = [str(year) for year in range(2024, 2012, -1)]

torch.classes.__path__ = []

if "visitor_count" not in st.session_state:
    st.session_state.visitor_count = 0

st.session_state.visitor_count += 1

if st.session_state.visitor_count > 10:
    st.warning("High traffic detected. Generation might take longer.")

if "generate_plot" not in st.session_state:
    st.session_state.generate_plot = False
if "results_cache" not in st.session_state:
    st.session_state.results_cache = {}

st.title("Shot Map Generator")
st.markdown(
    "Created by Anay Shukla | Twitter: [@BetterThanMario](https://twitter.com/BetterThanMario) | Bluesky: [@luigi1104.bsky.social](https://bsky.app/profile/luigi1104.bsky.social) | Email: anayshukla11@gmail.com"
)

st.header("About")
st.write(
    "Generates a shot map visualization of a player currently playing in the top 5 European leagues (PL, La Liga, Serie A, Bundesliga, Ligue 1) and RFPL. Data sourced from [Understat](https://understat.com)."
)

tab1, tab2, tab3 = st.tabs(["Main", "Output", "FAQ"])

with tab1:
    with st.container(height=320, border=True):
        input1 = st.selectbox(
            "Select player",
            options=player_names,
            index=None,
            placeholder="Type to search or select a player...",
        )

        season = st.selectbox("Select season", options=available_seasons, index=0)

        review_data = st.toggle(
            "Show FPL EV projection for the upcoming gameweek (Only for players currently playing in the Premier League)",
            value=False,
        )

        button = st.button("Generate Shot Map")

    st.info(
        "**Note:** Reminder that this is still a work in progress, will be making fixes with a few issues and also try to introduce new updates as well. Works perfectly for all players for the current season, however for players who played in a different league in any of the previous seasons will not yield accurate outputs, for instance, Kylian Mbappe's shot map for the 2023/24 season will be accurate, however, the other statistics will be inaccurate (as he was playing in Ligue 1 during that season). Hoping to fix it soon, sorry for the inconvience caused!"
    )

    if "fig" not in st.session_state:
        st.session_state.fig = None

    if button and input1 and season:
        cache_key = f"{input1.lower()}_{season}"
        if cache_key in st.session_state.results_cache:
            st.session_state.fig = st.session_state.results_cache[cache_key]
            st.session_state.generate_plot = True
            st.info("Retrieved from cache. Click on the Output tab to see the plot.")
        else:
            current_time = time.time()
            if (
                "last_request_time" in st.session_state
                and current_time - st.session_state.last_request_time < 30
            ):
                st.warning("Please wait 30 seconds between generating shot maps.")

            st.session_state.last_request_time = current_time

            if not season.isdigit() or len(season) != 4:
                st.error("Please enter a valid year.", icon=":material/error:")
            else:
                with st.spinner(
                    "Generating shot map, this will take a few minutes (feel free to browse through the FAQ section!)...",
                    show_time=True,
                ):
                    try:

                        def load_player_mappings():
                            with open(
                                "player_mappings.json", "r", encoding="utf-8"
                            ) as f:
                                return json.load(f)

                        closest = input1
                        new_df = players_data[players_data["name"] == closest]

                        # (The logic for player_id and league remains the same)
                        player_id = new_df.iloc[0, 0]
                        player_id = str(player_id)
                        league = new_df.iloc[0, 3]
                        league_name = new_df.iloc[0, 2]

                        client = understatapi.UnderstatClient()

                        shots_player = client.player(player=player_id).get_shot_data()

                        df_all_seasons = pd.DataFrame(shots_player)
                        available_seasons = df_all_seasons["season"].unique()

                        if season not in available_seasons:
                            seasons_list = ", ".join(sorted(available_seasons))
                            st.error(
                                f"No data found for {closest} in the {season}/{int(season) + 1} season. "
                                + f"Available seasons for this player: {seasons_list}",
                                icon="❌",
                            )
                            raise ValueError(f"No data for season {season}")

                        df = df_all_seasons[df_all_seasons["season"] == season]
                        player_name = df.iloc[1, 6]

                        if season == "2024" and league == "EPL" and review_data:
                            model = SentenceTransformer("models/all-MiniLM-L6-v2")
                            chrome_options = Options()
                            chrome_options.add_argument("--headless")
                            chrome_options.add_argument("--disable-gpu")
                            chrome_options.add_argument("--disable-logging")
                            chrome_options.add_argument("--silent")
                            chrome_options.add_argument("--disable-dev-shm-usage")
                            chrome_options.add_argument("--no-sandbox")
                            chrome_options.add_argument("--disable-extensions")

                            driver = webdriver.Chrome(
                                ChromeDriverManager().install(), options=chrome_options
                            )

                            url1 = "https://www.fplreview.com/free-planner/"
                            driver.get(url1)

                            time.sleep(15)

                            dropdown = Select(driver.find_element(By.ID, "myGroup"))
                            dropdown.select_by_visible_text("All Players")

                            checkbox = driver.find_element(By.ID, "checker")
                            if not checkbox.is_selected():
                                checkbox.click()

                            rows = driver.find_elements(By.CLASS_NAME, "playerRow")

                            num_rows = len(rows)

                            playlist = []

                            for row_num in range(1, num_rows - 1):
                                xpath = f'//*[@id="lightweight"]/tr[{row_num}]'
                                name = driver.find_element(
                                    By.XPATH, f'{xpath}/td[2]//div[@class="playerName"]'
                                ).text
                                price = driver.find_element(
                                    By.XPATH,
                                    f'{xpath}/td[2]//div[@class="playerDetails"]',
                                ).text
                                xmins = driver.find_element(
                                    By.XPATH, f"{xpath}/td[3]"
                                ).text
                                ev = driver.find_element(
                                    By.XPATH, f"{xpath}/td[4]"
                                ).text

                                player_data = {
                                    "name": name,
                                    "price": price,
                                    "xmins": xmins,
                                    "ev": ev,
                                }
                                playlist.append(player_data)
                            players_df = pd.DataFrame(playlist)
                            new_dict = load_player_mappings()
                            players_df["name"] = players_df["name"].replace(new_dict)
                            players_df["name"] = players_df["name"].str.lower()
                            df5 = players_df["name"].dropna().astype(str).tolist()

                            def matching2(closest, df5):
                                input_embedding = model.encode(closest)
                                df5_embeddings = model.encode(df5)
                                similarities = util.cos_sim(
                                    input_embedding, df5_embeddings
                                )
                                best_match_index = similarities.argmax().item()
                                best_match = df5[best_match_index]
                                if similarities.max() < 0.5:
                                    for name in df5:
                                        input_parts = closest.split()
                                        name_parts = name.split()

                                        if input_parts and name_parts:
                                            input_first_part = input_parts[0]
                                            name_first_part = name_parts[0]

                                            if jellyfish.metaphone(
                                                input_first_part
                                            ) == jellyfish.metaphone(name_first_part):
                                                return name
                                return best_match

                            evname = matching2(closest, df5)
                            ev_df = players_df[players_df["name"] == evname]
                            player_xmins = ev_df["xmins"].iloc[0]
                            player_price = ev_df["price"].iloc[0]
                            final_price = player_price[3:8]
                            player_ev = ev_df["ev"].iloc[0]
                        else:
                            pass

                        league_player_data = client.league(
                            league=league
                        ).get_player_data(season=season)
                        df1 = pd.DataFrame(league_player_data)

                        df2 = df1[df1["id"] == player_id]
                        df2 = df2.copy()
                        df2["xG"] = pd.to_numeric(df2["xG"])
                        df2["time"] = pd.to_numeric(df2["time"])
                        df2["shots"] = pd.to_numeric(df2["shots"])
                        df2["npxG"] = pd.to_numeric(df2["npxG"])
                        df2["xA"] = pd.to_numeric(df2["xA"])
                        df2["xGI"] = df2["xG"] + df2["xA"]
                        xg_p90 = df2["xG"].sum() / (df2["time"].sum() / 90)
                        shots_p90 = df2["shots"].sum() / (df2["time"].sum() / 90)
                        npxg_p90 = df2["npxG"].sum() / (df2["time"].sum() / 90)
                        xgi_p90 = df2["xGI"].sum() / (df2["time"].sum() / 90)

                        df["X"] = pd.to_numeric(df["X"])
                        df["Y"] = pd.to_numeric(df["Y"])
                        df["xG"] = pd.to_numeric(df["xG"])

                        df["X"] = df["X"] * 100
                        df["Y"] = df["Y"] * 100

                        number_of_shots = df.shape[0]
                        number_of_goals = df[df["result"] == "Goal"].shape[0]
                        number_of_xg = df["xG"].sum()
                        xg_per_shot = number_of_xg / float(number_of_shots)

                        background_color = "#484e48"
                        background_color2 = "#2c932f"

                        font_path = "lato/Lato-Regular.ttf"
                        font_props = fm.FontProperties(fname=font_path)

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
                            s=f"Shot Map for the {league_name} {season}/{int(season[2:4]) + 1} Season",
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
                            s=f"- Shot Saved",
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
                            s=f"- Blocked/Off Target",
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
                            s=f"- Goal",
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
                            s=f"- Penalty Scored",
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
                            s=f"- Penalty Missed",
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
                            s=f"- Freekick Scored",
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
                            s=f"xG per 90",
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
                            s=f"Shots per 90",
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
                            s=f"npxG per 90",
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
                            s=f"xGI per 90",
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
                                    if x["result"] == "Goal"
                                    and x["situation"] == "Penalty"
                                    else "violet"
                                    if x["result"] != "Goal"
                                    and x["situation"] == "Penalty"
                                    else "turquoise"
                                    if x["result"] == "Goal"
                                    and x["situation"] == "Freekick"
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
                            s=f"Total Shots",
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
                            s=f"Total Goals",
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
                            s=f"Total xG",
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
                            s=f"xG per Shot",
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

                        if league == "EPL" and season == "2024":
                            if review_data:
                                ax3.text(
                                    x=0.84,
                                    y=2.7,
                                    s=f"  Projections \n  this GW:",
                                    fontsize=18,
                                    fontproperties=font_props,
                                    fontweight="bold",
                                    color="white",
                                    ha="left",
                                )
                                ax3.text(
                                    x=0.85,
                                    y=1.2,
                                    s=f" xMins: {player_xmins} \n Price: {final_price} \n EV: {player_ev}",
                                    fontsize=18,
                                    fontproperties=font_props,
                                    fontweight="bold",
                                    color="white",
                                    ha="left",
                                )
                            else:
                                pass
                        else:
                            pass

                        ax3.text(
                            x=0.21,
                            y=0.05,
                            s=f"Viz by @BetterThanMario | Github: github.com/AnayShukla | Data: understat.com",
                            fontsize=10,
                            color="white",
                            alpha=0.7,
                        )

                        st.session_state.fig = fig
                        st.session_state.generate_plot = True

                        st.info(
                            "The shot map has been generated. Click on the Output tab to see the generated plot."
                        )

                        st.session_state.results_cache[cache_key] = st.session_state.fig

                    except Exception as e:
                        st.error(f"Error generating shot map: {str(e)}")
                        st.session_state.generate_plot = False

    elif button and season:
        st.warning("Please enter a player name first.", icon=":material/error:")

    elif button and input1:
        st.warning("Please enter a season first.", icon=":material/error:")

    elif button:
        st.warning(
            "Please enter a player name and season first.", icon=":material/error:"
        )

    if button:
        st.session_state.generate_plot = True

with tab2:
    st.header("Output")
    st.markdown(
        "Any doubts regarding the output generated? Or bored while waiting? Head over to the FAQ tab to learn more about the project."
    )

    st.subheader("Your Shot Map will be generated here:")

    if st.session_state.generate_plot and st.session_state.fig:
        st.pyplot(st.session_state.fig, use_container_width=False)
        file_name = f"{input1}_{season}_shot_map.png"

        buf = BytesIO()
        st.session_state.fig.savefig(buf, format="png", bbox_inches="tight", dpi=300)
        buf.seek(0)

        st.download_button(
            label="Download the Shot Map (PNG)",
            data=buf.getvalue(),
            file_name=file_name,
            mime="image/png",
        )

    else:
        st.info(
            "Please enter valid inputs in the Main tab and click 'Generate Plot' to see results here."
        )

with tab3:
    what_is_a_shot_map = """A shot map is a visual representation of a player's shots taken during a match or over a season. It typically shows the location of each shot on the pitch, along with additional information such as whether the shot was on target, off target, or resulted in a goal. Shot maps are useful for analyzing a player's shooting performance and understanding their scoring opportunities, primarily (but not limited to) useful for players in the attacking roles."""
    how_is_it_useful = """Shot maps are useful for analyzing a player's ability to finish and understanding their attacking output. It essentially is a graphical representation of the quality of scoring opportunities a player avails to himself. Keen data-loving fans and even the general public can use this to assist their own work or develop a deeper understanding about a players' scoring ability."""
    what_is_xg = """xG, or expected goals, is a metric used in football to assess the quality of scoring chances. It assigns a value to each shot based on various factors such as shot location, angle, type of chance, etc. The xG value represents the likelihood of a shot resulting in a goal, with higher values indicating better chances. xG is useful for evaluating player performance and team attacking efficiency."""
    what_is_npxg = """npxG, or non-penalty expected goals, is a variant of the xG metric that excludes penalty kicks. It focuses solely on the quality of scoring chances from open play and set pieces, providing a clearer picture of a player's goal-scoring ability without the influence of penalties which tend to be shots with very high xG."""
    what_is_xgi = """xGI, or expected goal involvements, is a metric that combines a player's expected goals (xG) and expected assists (xA) into a single value. It measures a player's overall attacking contribution by considering both their goal-scoring opportunities and their ability to create chances for teammates."""
    what_is_per90 = """Per 90 refers to statistics that are normalized to a 90-minute match duration. It allows for fair comparisons between players or teams regardless of the number of minutes played. However, it is important to note that sometimes per 90 stats can be misleading if a player has played significantly fewer minutes than others, as they may not accurately reflect their overall performance."""
    what_are_the_circles = """The circles on the shot map represent the quality of the scoring chance. The size of the circle indicates the xG value of the shot, with larger circles representing higher xG values. The color of the circle indicates the result of the shot, such as a goal (red), saved shot (yellow), blocked/off target (colourless), penalty scored (blue square), penalty missed (pink square), and freekick scored (turquoise triangle)."""

    st.markdown("### Frequently Asked Questions (FAQ)")
    with st.expander("What is a shot map?"):
        st.write(what_is_a_shot_map)

    with st.expander("How can I use it?"):
        st.write(how_is_it_useful)

    with st.expander("What is xG?"):
        st.write(what_is_xg)

    with st.expander("What is npxG?"):
        st.write(what_is_npxg)

    with st.expander("What is xGI?"):
        st.write(what_is_xgi)

    with st.expander("Why are all the metrics in 'per 90'?"):
        st.write(what_is_per90)

    with st.expander("What does the size of the shape indicate?"):
        st.write(what_are_the_circles)

    st.markdown("---")
    st.markdown("""
    ## Shot Map Legend
    #### **Shapes**
    - **Dot Size**: Larger dots represent higher xG (expected goal) value chances
    - **Circle**: All shots taken in open play or from corners
    - **Square**: Penalty shots taken
    - **Triangle**: Free kick shots taken
    
    #### **Colors**
    - Red: Goal
    - Yellow: Saved shot
    - Blue: Penalty scored
    - Violet: Penalty missed
    - Turquoise: Free kick scored
    - Default: Blocked/missed shots

    #### **Stats Explained**
    - **xG (Expected Goals)**: Probability of scoring based on shot quality
    - **npxG**: Non-penalty expected goals
    - **xGI**: Expected goal involvements (xG + xA)
    - **xA**: Expected assists
        """)


st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: gray; font-size: 0.8em;'>
    By Anay Shukla | Data provided by Understat.com 
    </div>
    """,
    unsafe_allow_html=True,
)
