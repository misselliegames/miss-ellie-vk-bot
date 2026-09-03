from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image

from question_sets import QUESTION_SETS


ROOT = Path(__file__).resolve().parents[1]

SOURCE_FILES = {
    "3-4": [
        ("Movers_01_daughter_his.png", "Movers_01_daughter_his.png", "OK", "Scene verified: Sultan and daughter."),
        ("02\t_eastern_princess_happy.png", "Movers_02_eastern_princess_happy.png", "RENAMED", "Filename normalized; scene verified."),
        ("Movers_03_eastern_market_doll_five.png", "Movers_03_eastern_market_doll_five.png", "OK", "Scene verified: seller, Toto and doll."),
        ("movers_04_baba_yaga_koschei_getting_dressed.jpg", "movers_04_baba_yaga_koschei_getting_dressed.png", "RENAMED", "PNG source used for the approved scene."),
        ("movers_05_animal_city_fox_rabbit.jpg", "movers_05_animal_city_fox_rabbit.png", "RENAMED", "PNG source used; height contrast verified."),
        ("movers_06_animal_city_sloth_drivers.png", "movers_06_animal_city_sloth_drivers.png", "OK", "Fast red car scene verified."),
        ("Movers_ 07_anime_city_girl_icecream.png", "Movers_07_anime_city_girl_icecream.png", "RENAMED", "Whitespace normalized; café scene verified."),
        ("Movers_ 08_anime_city_offer_icecream.png", "Movers_08_anime_city_offer_icecream.png", "RENAMED", "Whitespace normalized; offered ice cream verified."),
        ("Movers_09_fantasy_anime_flying_girl.png", "Movers_09_fantasy_anime_flying_girl.png", "OK", "Flying traveller and city verified."),
        ("Movers_ 10_fantasy_anime_climbing_traveler.png", "Movers_10_fantasy_anime_climbing_traveler.png", "RENAMED", "Whitespace normalized; climbing scene verified."),
        ("Movers_ 11_magic_school_cat_on_bed.png", "Movers_ 11_magic_school_cat_on_bed.png", "RENAMED", "Whitespace normalized; cat in bedroom verified."),
        ("Movers_12_magic_school_two_books_table.png", "Movers_12_magic_school_two_books_table.png", "OK", "Exactly two books on the table verified."),
        ("Movers_13_magic_school_golden_ball.png", "Movers_13_magic_school_golden_ball.png", "OK", "Golden ball and prohibition sign verified."),
        ("movers_14_baba_yaga_koschei_housework.png", "movers_14_baba_yaga_koschei_housework.png", "OK", "Dirty dishes scene verified."),
        ("Movers_15_nu_pogodi_wolf_tshirt.png", "Movers_15_nu_pogodi_wolf_tshirt.png", "OK", "Wolf in T-shirt verified."),
        ("Movers_16_nu_pogodi_hare_eating.png", "Movers_16_nu_pogodi_hare_eating.png", "OK", "Hare eating scene verified; source already horizontal."),
        ("Movers_17_block_game_three_foxes.jpg", "Movers_17_block_game_three_foxes.png", "RENAMED", "PNG source used; three foxes verified."),
        ("Movers_18_block_game_mouse_cheese.png", "Movers_18_block_game_mouse_cheese.png", "OK", "Mouse and large amount of cheese verified."),
        ("movers_19_minecraft_build_house.png", "movers_19_minecraft_build_house.png", "OK", "Prepared building site verified."),
        ("movers_20_minecraft_creeper.png", "movers_20_minecraft_creeper.png", "OK", "Sudden Creeper scene verified."),
    ],
    "5-6": [
        ("Movers_01_daughter_his.png", "Movers_01_daughter_his.png", "OK", "Sultan, daughter and necklace verified."),
        ("56_02_eastern_market_doll_47.png", "56_02_eastern_market_doll_47.png", "OK", "Single price 47 verified."),
        ("56_03_eastern_boy_magic_carpet.png", "56_03_eastern_boy_magic_carpet.png", "OK", "Boy flying on magic carpet verified."),
        ("56_04_baba_yaga_magic_carpet.png", "56_04_baba_yaga_magic_carpet.png", "OK", "Baba Yaga travelling by air verified."),
        ("56_05_baba_yaga_breakfast.png", "56_05_baba_yaga_breakfast.png", "OK", "Sausages and mash, no cereal, verified."),
        ("56_06_magic_school_flying_match.png", "56_06_magic_school_flying_match.png", "OK", "Helmet, gloves and broom verified."),
        ("56_07_magic_school_potion.png", "56_07_magic_school_potion.png", "OK", "Mushrooms on table verified."),
        ("movers_05_animal_city_fox_rabbit.png", "movers_05_animal_city_fox_rabbit.png", "OK", "Fox, rabbit and green shirt verified."),
        ("movers_06_animal_city_sloth_drivers.png", "movers_06_animal_city_sloth_drivers.png", "OK", "Fast red car verified."),
        ("56_10_baba_yaga_highest_loudest.png", "56_10_baba_yaga_highest_loudest.png", "OK", "Baba Yaga highest and singing verified."),
        ("56_11_anime_city_friends_go_cycling.png", "56_11_anime_city_friends_go_cycling.png", "OK", "Four friends cycling together verified."),
        ("56_12_anime_found_food.png", "56_12_anime_found_food.png", "OK", "Apples and bread for trip verified."),
        ("56_13_anime_battle.png", "56_13_anime_battle.png", "OK", "Centered self-protection scene verified; unseen threat."),
        ("56_14_hiccup_tail_mechanism.png", "56_14_hiccup_tail_mechanism.png", "OK", "Rider, tail control cable and prosthetic fin verified."),
        ("56_15_dragon_flight_club_secret.png", "56_15_dragon_flight_club_secret.png", "OK", "Secret club and shushing gesture verified."),
        ("movers_14_baba_yaga_koschei_housework.png", "movers_14_baba_yaga_koschei_housework.png", "OK", "Dirty dishes scene verified."),
        ("56_17_superhero_interactive_city_map.png", "56_17_superhero_interactive_city_map.png", "OK", "START, FINISH, zebra crossing, pavement and three-step route verified."),
        ("56_18_miles_meets_gwen_tuesday.png", "56_18_miles_meets_gwen_tuesday.png", "OK", "Agreed meeting and exact Tuesday text verified."),
        ("movers_19_minecraft_build_house.png", "movers_19_minecraft_build_house.png", "OK", "Prepared building site verified."),
        ("movers_20_minecraft_creeper.png", "movers_20_minecraft_creeper.png", "OK", "Sudden help decision verified."),
    ],
}


def main() -> None:
    records = []
    used_targets = set()
    for route in ("3-4", "5-6"):
        questions = QUESTION_SETS[route]
        if len(questions) != len(SOURCE_FILES[route]):
            raise RuntimeError(f"Manifest mapping count mismatch for {route}")
        for question, source in zip(questions, SOURCE_FILES[route]):
            expected, found, status, notes = source
            target = Path("assets") / "questions" / route / question["image"]
            full_target = ROOT / target
            if target.as_posix() in used_targets:
                raise RuntimeError(f"Target assigned twice: {target}")
            used_targets.add(target.as_posix())
            with Image.open(full_target) as image:
                image.verify()
            with Image.open(full_target) as image:
                width, height = image.size
                image_format = image.format
            records.append({
                "route": route,
                "question_number": question["id"],
                "expected_image": expected,
                "found_image": found,
                "source_location": f"Pics {route}/{found}",
                "target_location": target.as_posix(),
                "match_status": status,
                "notes": notes,
                "exists": full_target.exists(),
                "opens": True,
                "width": width,
                "height": height,
                "format": image_format,
                "sha256": hashlib.sha256(full_target.read_bytes()).hexdigest(),
            })
    output = ROOT / "asset_manifest.json"
    output.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(records)} verified records to {output.name}")


if __name__ == "__main__":
    main()
