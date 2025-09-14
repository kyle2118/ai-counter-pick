from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict, List, Optional
import json
import random
import time
from functools import lru_cache
from app.util import readHeroNames
from app.scraper import scrape_hero



app = FastAPI()

heroes = readHeroNames('app/heroes.json')

# Cache for hero data to avoid re-scraping
@lru_cache(maxsize=128)
def get_cached_hero_data(hero_name: str):
    """Get hero data with caching to improve performance"""
    return scrape_hero(hero_name)

class PickRequest(BaseModel):
    team: str
    pos: int
    picks: Dict[str, List[str]]

@app.post("/recommend")
def recommend(data: PickRequest):
    """
    Recommend heroes based on current picks.
    Returns heroes that are good against enemy picks and synergize with team picks.
    """
    my_team_picks = data.picks[data.team]
    enemy_team_picks = data.picks["radiant" if data.team == "dire" else "dire"]
    
    if not my_team_picks:
        return {"recommended": [], "worst": []}
    
    # Get all hero data for analysis
    all_picked = my_team_picks + enemy_team_picks
    hero_scores = {}
    
    # Analyze enemy counters
    enemy_counter_scores = analyze_enemy_counters(enemy_team_picks)
    
    # Analyze team synergy
    team_synergy_scores = analyze_team_synergy(my_team_picks)
    
    # Combine scores for each available hero
    for hero in heroes:
        if hero not in all_picked:
            counter_score = enemy_counter_scores.get(hero, 0)
            synergy_score = team_synergy_scores.get(hero, 0)
            
            # Weighted combination: 70% counter-pick, 30% synergy
            total_score = (counter_score * 0.7) + (synergy_score * 0.3)
            hero_scores[hero] = total_score
    
    # Sort heroes by combined score
    sorted_heroes = sorted(hero_scores.items(), key=lambda x: x[1], reverse=True)
    
    # Separate best and worst recommendations
    best_recommendations = [hero for hero, score in sorted_heroes[:10] if score > 0]
    worst_recommendations = [hero for hero, score in sorted_heroes[-10:] if score < 0]
    
    return {
        "recommended": best_recommendations,
        "worst": worst_recommendations
    }

def analyze_enemy_counters(enemy_team_picks):
    """Analyze which heroes are good against enemy picks"""
    hero_scores = {}
    
    for enemy_hero in enemy_team_picks:
        enemy_data = get_cached_hero_data(enemy_hero)
        
        # Heroes that are good against this enemy get positive score
        for counter_hero in enemy_data["worst_against"]:
            hero_scores[counter_hero] = hero_scores.get(counter_hero, 0) + 1
        
        # Heroes that are bad against this enemy get negative score
        for weak_hero in enemy_data["best_against"]:
            hero_scores[weak_hero] = hero_scores.get(weak_hero, 0) - 1
        
        # Reduced delay for better performance
        time.sleep(0.3)
    
    return hero_scores

def analyze_team_synergy(my_team_picks):
    """Analyze which heroes synergize well with team picks"""
    hero_scores = {}
    
    for team_hero in my_team_picks:
        team_hero_data = get_cached_hero_data(team_hero)
        
        # Heroes that are good WITH our team hero get positive score
        # (These are heroes that our team hero is good against, meaning they work well together)
        for synergy_hero in team_hero_data["best_against"]:
            hero_scores[synergy_hero] = hero_scores.get(synergy_hero, 0) + 0.5
        
        # Reduced delay for better performance
        time.sleep(0.3)
    
    return hero_scores
