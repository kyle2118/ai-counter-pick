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
    Recommend heroes based on current picks with enhanced data for LLM analysis.
    Returns heroes that are good against enemy picks and synergize with team picks.
    """
    my_team_picks = data.picks[data.team]
    enemy_team_picks = data.picks["radiant" if data.team == "dire" else "dire"]
    
    if not my_team_picks:
        return {"recommended": [], "worst": []}
    
    # Prepare comprehensive context for enhanced analysis
    context = prepare_llm_context(my_team_picks, enemy_team_picks, data.pos)
    
    # Get all hero data for analysis
    all_picked = my_team_picks + enemy_team_picks
    hero_scores = {}
    
    # Analyze enemy counters with enhanced data
    enemy_counter_scores = analyze_enemy_counters_enhanced(enemy_team_picks, context)
    
    # Analyze team synergy with enhanced data
    team_synergy_scores = analyze_team_synergy_enhanced(my_team_picks, context)
    
    # Combine scores for each available hero (only score heroes that appear in counter/synergy analysis)
    scored_heroes = set(enemy_counter_scores.keys()) | set(team_synergy_scores.keys())
    
    for hero in scored_heroes:
        if hero not in all_picked:
            counter_score = enemy_counter_scores.get(hero, 0)
            synergy_score = team_synergy_scores.get(hero, 0)
            
            # Enhanced scoring with position and meta considerations
            position_bonus = get_position_bonus(hero, data.pos, context)
            meta_bonus = get_meta_bonus(hero, context)
            
            # Weighted combination: 50% counter-pick, 30% synergy, 15% position, 5% meta
            total_score = (counter_score * 0.5) + (synergy_score * 0.3) + (position_bonus * 0.15) + (meta_bonus * 0.05)
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

def analyze_enemy_counters_enhanced(enemy_team_picks, context):
    """Enhanced enemy counter analysis using rich context data"""
    hero_scores = {}
    
    for enemy_hero in enemy_team_picks:
        enemy_data = context["hero_data"].get(enemy_hero, {})
        
        # Base counter scoring
        for counter_hero in enemy_data.get("worst_against", []):
            hero_scores[counter_hero] = hero_scores.get(counter_hero, 0) + 1
        
        for weak_hero in enemy_data.get("best_against", []):
            hero_scores[weak_hero] = hero_scores.get(weak_hero, 0) - 1
        
        # Enhanced scoring based on enemy threat level
        threat_level = next((t["threat_level"] for t in context["meta_analysis"]["enemy_threats"] if t["hero"] == enemy_hero), "Medium")
        threat_multiplier = 1.5 if threat_level == "High" else 1.0
        
        # Apply threat multiplier to scores
        for hero in hero_scores:
            if hero in enemy_data.get("worst_against", []):
                hero_scores[hero] *= threat_multiplier
    
    return hero_scores

def analyze_team_synergy_enhanced(my_team_picks, context):
    """Enhanced team synergy analysis using rich context data"""
    hero_scores = {}
    
    for team_hero in my_team_picks:
        team_hero_data = context["hero_data"].get(team_hero, {})
        
        # Base synergy scoring
        for synergy_hero in team_hero_data.get("best_against", []):
            hero_scores[synergy_hero] = hero_scores.get(synergy_hero, 0) + 0.5
        
        # Enhanced scoring based on team needs (NO additional scraping)
        team_needs = context["meta_analysis"]["team_composition"]["needs"]
        for hero in hero_scores:
            # Only apply bonus if we already have data for this hero
            if hero in context["hero_data"]:
                hero_data = context["hero_data"][hero]
                if hero_data.get("role") in team_needs:
                    hero_scores[hero] *= 1.3  # Bonus for filling team needs
    
    return hero_scores

def get_position_bonus(hero, position, context):
    """Calculate position-specific bonus for hero (using cached data only)"""
    # Use cached data from context instead of making new requests
    hero_data = context["hero_data"].get(hero, {})
    if not hero_data:
        # If not in context, get from cache (this should be rare)
        hero_data = get_cached_hero_data(hero)
    
    bonus = 0
    
    # Check if hero fits position requirements
    if position == 1 and hero_data.get("role") == "Carry":
        bonus += 2
    elif position == 2 and hero_data.get("role") in ["Mid", "Ganker"]:
        bonus += 2
    elif position == 3 and hero_data.get("role") in ["Offlane", "Initiator"]:
        bonus += 2
    elif position in [4, 5] and hero_data.get("role") == "Support":
        bonus += 2
    
    return bonus

def get_meta_bonus(hero, context):
    """Calculate meta-based bonus for hero (using cached data only)"""
    # Use cached data from context instead of making new requests
    hero_data = context["hero_data"].get(hero, {})
    if not hero_data:
        # If not in context, get from cache (this should be rare)
        hero_data = get_cached_hero_data(hero)
    
    bonus = 0
    
    # Win rate bonus
    win_rate = hero_data.get("win_rate", "50%")
    if win_rate and win_rate != "50%":
        try:
            rate = float(win_rate.replace("%", ""))
            if rate > 55:
                bonus += 1
            elif rate < 45:
                bonus -= 1
        except:
            pass
    
    return bonus

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

def prepare_llm_context(my_team_picks, enemy_team_picks, position):
    """Prepare comprehensive context data for LLM analysis"""
    # Collect detailed data for all picked heroes FIRST
    all_picked = my_team_picks + enemy_team_picks
    hero_data = {}
    for hero in all_picked:
        hero_data[hero] = get_cached_hero_data(hero)
        time.sleep(0.3)  # Rate limiting
    
    context = {
        "my_team": my_team_picks,
        "enemy_team": enemy_team_picks,
        "my_position": position,
        "hero_data": hero_data,
        "available_heroes": [h for h in heroes if h not in all_picked],
        "meta_analysis": {
            "team_composition": analyze_team_composition(my_team_picks, hero_data),
            "enemy_threats": analyze_enemy_threats(enemy_team_picks, hero_data),
            "position_needs": get_position_requirements(position)
        }
    }
    
    return context

def analyze_team_composition(my_team_picks, hero_data):
    """Analyze team composition strengths and weaknesses"""
    if not my_team_picks:
        return {"analysis": "No team picks yet", "needs": ["Any hero"]}
    
    # Basic composition analysis using provided hero_data
    roles = []
    attributes = []
    
    for hero in my_team_picks:
        hero_info = hero_data.get(hero, {})
        if hero_info.get("role"):
            roles.append(hero_info["role"])
        if hero_info.get("primary_attribute"):
            attributes.append(hero_info["primary_attribute"])
    
    return {
        "current_roles": roles,
        "current_attributes": attributes,
        "needs": determine_team_needs(roles, attributes)
    }

def analyze_enemy_threats(enemy_team_picks, hero_data):
    """Analyze threats posed by enemy team"""
    threats = []
    for hero in enemy_team_picks:
        hero_info = hero_data.get(hero, {})
        threats.append({
            "hero": hero,
            "win_rate": hero_info.get("win_rate", "Unknown"),
            "role": hero_info.get("role", "Unknown"),
            "threat_level": "High" if hero_info.get("win_rate", "0%").replace("%", "") > "55" else "Medium"
        })
    
    return threats

def get_position_requirements(position):
    """Get requirements for specific position"""
    position_roles = {
        1: "Carry - Late game damage dealer",
        2: "Mid - Solo lane, ganker, initiator", 
        3: "Offlane - Tanky initiator, space creator",
        4: "Support - Roaming, warding, team fights",
        5: "Support - Lane support, babysitter"
    }
    
    return {
        "position": position,
        "role": position_roles.get(position, "Unknown"),
        "typical_needs": get_position_specific_needs(position)
    }

def determine_team_needs(roles, attributes):
    """Determine what the team needs based on current picks"""
    needs = []
    
    if "Support" not in roles:
        needs.append("Support")
    if "Carry" not in roles:
        needs.append("Carry")
    if len([a for a in attributes if a == "Intelligence"]) < 2:
        needs.append("Intelligence hero")
    
    return needs

def get_position_specific_needs(position):
    """Get specific needs for each position"""
    needs_map = {
        1: ["Damage", "Farm", "Late game scaling"],
        2: ["Ganking", "Initiating", "Mid game power"],
        3: ["Tankiness", "Initiating", "Space creation"],
        4: ["Roaming", "Warding", "Team fight"],
        5: ["Lane support", "Warding", "Protection"]
    }
    
    return needs_map.get(position, ["General utility"])

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
