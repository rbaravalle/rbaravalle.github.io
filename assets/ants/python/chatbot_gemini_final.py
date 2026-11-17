import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from enum import Enum
import random

# =========================
# Parameters (ANTI-CLUMPING)
# =========================
WORLD_SIZE = 70
N_ANTS = 60

# DECAY is the most important factor to prevent clumps.
# It must be high enough that "bad loops" fade away quickly.
PHEROMONE_DECAY = 0.05   
PHEROMONE_DEPOSIT = 5.0
PHEROMONE_DIFFUSION = 0.1

# SENSITIVITY needs to be balanced. Too high = clumps. Too low = chaos.
SENSITIVITY = 2.5 
RANDOMNESS = 0.05 

INITIAL_FOOD = 500

# =========================
# Ant States
# =========================
class State(Enum):
    SEARCHING = 0
    CARRYING = 1

# =========================
# World
# =========================
class World:
    def __init__(self, size, nest_pos):
        self.size = size
        self.food_source = np.zeros((size, size))
        self.food_nest = np.zeros((size, size))
        self.nest = np.zeros((size, size))
        
        # Pheromone A: "I found food, follow me!" (Red)
        self.pheromone_food = np.zeros((size, size)) 
        
        # Pheromone B: "I'm exploring, this way home" (Blue)
        self.pheromone_home = np.zeros((size, size))
        
        self.total_collected = 0

        # Create a "Gradient Field" pointing to the nest
        # This acts as a global compass so they never get TOTALLY lost
        xx, yy = np.meshgrid(np.arange(size), np.arange(size), indexing="ij")
        self.nest_distance = np.sqrt((xx - nest_pos[0])**2 + (yy - nest_pos[1])**2)
        # Normalize: 0 at nest, 1 at edge
        self.nest_distance /= self.nest_distance.max()

    def update_pheromones(self):
        # We apply diffusion and decay to both pheromone grids
        for phero in [self.pheromone_food, self.pheromone_home]:
            # Diffusion (spread out)
            laplacian = (
                np.roll(phero, 1, 0) + np.roll(phero, -1, 0) +
                np.roll(phero, 1, 1) + np.roll(phero, -1, 1) -
                4 * phero
            )
            phero += PHEROMONE_DIFFUSION * laplacian
            
            # Decay (evaporate)
            phero *= (1.0 - PHEROMONE_DECAY)
            
            # Hard clip to prevent infinite buildup
            np.clip(phero, 0, 100, out=phero)

# =========================
# Ant
# =========================
class Ant:
    def __init__(self, world, nest_pos):
        self.world = world
        self.x, self.y = nest_pos
        self.state = State.SEARCHING
        self.carrying_food = False
        
        # Inertia: Ants prefer to keep moving in their current direction
        self.last_dx = 0
        self.last_dy = 0

    def step(self):
        # 1. Deposit Pheromones (Mark where we are)
        if self.state == State.CARRYING:
            # Drop "Food" pheromone (intense) to mark the path
            self.world.pheromone_food[self.x, self.y] += PHEROMONE_DEPOSIT
        else:
            # Drop "Home" pheromone (weaker) so others can backtrack
            self.world.pheromone_home[self.x, self.y] += PHEROMONE_DEPOSIT * 0.2

        # 2. Decide and Move
        self.move()

        # 3. Check Interactions
        # Found Food?
        if self.state == State.SEARCHING and self.world.food_source[self.x, self.y] >= 1:
            self.world.food_source[self.x, self.y] -= 1
            self.state = State.CARRYING
            self.carrying_food = True
            # Flip direction immediately to return home
            self.last_dx *= -1
            self.last_dy *= -1
        
        # Found Nest?
        elif self.state == State.CARRYING and self.world.nest[self.x, self.y] == 1:
            self.state = State.SEARCHING
            self.carrying_food = False
            self.world.food_nest[self.x, self.y] += 1
            self.world.total_collected += 1
            # Flip direction to go back to food
            self.last_dx *= -1
            self.last_dy *= -1

    def move(self):
        directions = [
            (-1, 0), (1, 0), (0, -1), (0, 1),
            (-1, -1), (-1, 1), (1, -1), (1, 1)
        ]

        scores = []
        valid_idxs = []

        for i, (dx, dy) in enumerate(directions):
            nx, ny = self.x + dx, self.y + dy

            # Bounds check
            if 0 <= nx < self.world.size and 0 <= ny < self.world.size:
                
                # --- CALCULATION OF DESIRE ---
                score = 0
                
                # 1. Pheromone Attraction (Logarithmic to prevent clamping)
                if self.state == State.SEARCHING:
                    # Look for RED (Food) pheromone
                    phero = self.world.pheromone_food[nx, ny]
                    # Logarithmic sensing: log(1+x). This means 100 is not 10x better than 10.
                    # It creates a plateau so ants don't get stuck on max values.
                    score += SENSITIVITY * np.log1p(phero)
                else:
                    # Look for BLUE (Home) pheromone
                    phero = self.world.pheromone_home[nx, ny]
                    score += SENSITIVITY * np.log1p(phero)
                    
                    # 2. Static Compass (Only heavily used when returning home)
                    # This pulls them to the center even if pheromones fail
                    dist_score = -2.0 * self.world.nest_distance[nx, ny]
                    score += dist_score

                # 3. Momentum (Inertia)
                # Dot product to reward continuing straight
                # (Prevents jittering back and forth)
                if self.last_dx != 0 or self.last_dy != 0:
                    dot = dx * self.last_dx + dy * self.last_dy
                    # Penalize moving backwards heavily
                    if dot < 0: score -= 2.0
                    # Reward moving straight slightly
                    if dot > 0: score += 0.5
                
                scores.append(score)
                valid_idxs.append(i)

        # Convert to probabilities
        scores = np.array(scores)
        
        # Softmax stability trick
        scores = scores - scores.max() 
        probs = np.exp(scores)
        
        # Add noise floor (RANDOMNESS)
        # This ensures there is ALWAYS a small chance to pick a random direction
        # even if one direction is very good. This breaks loops.
        probs += RANDOMNESS
        probs /= probs.sum()

        # Pick direction
        choice = np.random.choice(valid_idxs, p=probs)
        dx, dy = directions[choice]
        
        self.x += dx
        self.y += dy
        self.last_dx = dx
        self.last_dy = dy

# =========================
# Setup
# =========================
nest_x, nest_y = WORLD_SIZE // 2, WORLD_SIZE // 2
world = World(WORLD_SIZE, (nest_x, nest_y))

# Define Nest Area
world.nest[nest_x-2:nest_x+3, nest_y-2:nest_y+3] = 1

# Define Food Areas (2 patches to encourage splitting)
world.food_source[10:20, 10:20] = INITIAL_FOOD * 0.5
world.food_source[50:60, 50:60] = INITIAL_FOOD * 0.5

ants = [Ant(world, (nest_x, nest_y)) for _ in range(N_ANTS)]

# =========================
# Visualization
# =========================
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 6))

# Pre-allocate image data
img_data = np.zeros((WORLD_SIZE, WORLD_SIZE, 3))
im1 = ax1.imshow(img_data, interpolation="nearest")
ax1.set_title("Ant Colony (Red=Food Trail, Blue=Home Trail)")
ax1.axis("off")

# Bar chart
bars = ax2.bar(['Food Remaining', 'Food at Nest'], [INITIAL_FOOD, 0], color=['green', 'blue'])
ax2.set_ylim(0, INITIAL_FOOD)

def render():
    img = np.zeros((WORLD_SIZE, WORLD_SIZE, 3))
    
    # 1. Pheromones
    # Red channel = Food Pheromone
    img[..., 0] = np.clip(world.pheromone_food / 20.0, 0, 1.0)
    # Blue channel = Home Pheromone (mixed with green for Cyan)
    img[..., 2] = np.clip(world.pheromone_home / 20.0, 0, 1.0)
    
    # 2. Food (Green blocks)
    food_mask = world.food_source > 0
    img[food_mask, 1] = 1.0
    
    # 3. Nest (Blue block)
    nest_mask = world.nest > 0
    img[nest_mask, 2] = 1.0
    
    # 4. Ants
    for ant in ants:
        if ant.carrying_food:
            img[ant.x, ant.y] = [1, 1, 0] # Yellow
        else:
            img[ant.x, ant.y] = [1, 1, 1] # White
            
    return img

def update(frame):
    # Simulation steps
    for ant in ants:
        ant.step()
    
    world.update_pheromones()
    
    # Update Graphics
    im1.set_data(render())
    
    current_food = world.food_source.sum()
    collected = world.total_collected
    
    bars[0].set_height(current_food)
    bars[1].set_height(collected)
    
    ax1.set_title(f"Progress: {collected}/{int(INITIAL_FOOD)}")
    
    return [im1, bars[0], bars[1]]

ani = FuncAnimation(fig, update, interval=20, blit=True)
plt.show()