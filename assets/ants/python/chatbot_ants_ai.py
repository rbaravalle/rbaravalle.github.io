import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from enum import Enum
import random

# =========================
# Parameters
# =========================
WORLD_SIZE = 70
N_ANTS = 50

PHEROMONE_DEPOSIT = 15.0
PHEROMONE_DECAY = 0.003
PHEROMONE_DIFFUSION = 0.08

SENSITIVITY = 4.0
RANDOMNESS = 0.2

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
        
        # TWO TYPES of pheromones - this is the key!
        self.pheromone_to_food = np.zeros((size, size))  # Left by ants going TO food
        self.pheromone_to_nest = np.zeros((size, size))  # Left by ants returning TO nest
        
        self.total_collected = 0

        # Distance-to-nest field (static compass for initial guidance)
        xx, yy = np.meshgrid(np.arange(size), np.arange(size), indexing="ij")
        self.nest_distance = np.sqrt(
            (xx - nest_pos[0])**2 + (yy - nest_pos[1])**2
        )

    def diffuse_pheromones(self):
        # Diffuse both pheromone types
        for pheromone in [self.pheromone_to_food, self.pheromone_to_nest]:
            laplacian = (
                np.roll(pheromone, 1, 0) +
                np.roll(pheromone, -1, 0) +
                np.roll(pheromone, 1, 1) +
                np.roll(pheromone, -1, 1) -
                4 * pheromone
            )
            pheromone += PHEROMONE_DIFFUSION * laplacian
            pheromone *= (1.0 - PHEROMONE_DECAY)
            np.clip(pheromone, 0, 300, out=pheromone)

# =========================
# Ant
# =========================
class Ant:
    def __init__(self, world, nest_pos):
        self.world = world
        self.x, self.y = nest_pos
        self.state = State.SEARCHING
        self.carrying_food = False

    def step(self):
        # Deposit the RIGHT pheromone based on state
        if self.state == State.CARRYING:
            # Carrying food back -> leave "to nest" pheromone for other searching ants
            self.world.pheromone_to_nest[self.x, self.y] += PHEROMONE_DEPOSIT
        else:
            # Searching for food -> leave weak "to food" pheromone
            self.world.pheromone_to_food[self.x, self.y] += PHEROMONE_DEPOSIT * 0.05

        self.move()

        # Pick up food when searching
        if self.state == State.SEARCHING and self.world.food_source[self.x, self.y] > 0:
            self.world.food_source[self.x, self.y] -= 1
            self.state = State.CARRYING
            self.carrying_food = True

        # Deliver food at nest
        if self.state == State.CARRYING and self.world.nest[self.x, self.y] == 1:
            self.state = State.SEARCHING
            self.carrying_food = False
            self.world.food_nest[self.x, self.y] += 1
            self.world.total_collected += 1

    def move(self):
        directions = [
            (-1, 0), (1, 0), (0, -1), (0, 1),
            (-1, -1), (-1, 1), (1, -1), (1, 1)
        ]

        scores = []
        valid_dirs = []

        for dx, dy in directions:
            nx, ny = self.x + dx, self.y + dy
            if 0 <= nx < self.world.size and 0 <= ny < self.world.size:
                if self.state == State.SEARCHING:
                    # Follow "to nest" pheromone (left by successful ants returning)
                    # This leads you TO the food
                    pheromone_score = SENSITIVITY * self.world.pheromone_to_nest[nx, ny]
                    # Small penalty for going away from where food might be
                    distance_penalty = 0.1 * self.world.nest_distance[nx, ny]
                    score = pheromone_score - distance_penalty
                else:
                    # Follow "to food" pheromone backwards (guides you home)
                    # Plus strong attraction to nest
                    pheromone_score = SENSITIVITY * 0.3 * self.world.pheromone_to_food[nx, ny]
                    nest_attraction = -1.0 * self.world.nest_distance[nx, ny]
                    score = pheromone_score + nest_attraction

                scores.append(score)
                valid_dirs.append((dx, dy))

        scores = np.array(scores, dtype=np.float64)

        # Numerically stable softmax
        scores -= scores.max()
        weights = np.exp(scores)
        weights += RANDOMNESS
        weights /= weights.sum()

        dx, dy = valid_dirs[np.random.choice(len(valid_dirs), p=weights)]
        self.x = np.clip(self.x + dx, 0, self.world.size - 1)
        self.y = np.clip(self.y + dy, 0, self.world.size - 1)

# =========================
# Setup
# =========================
nest_x, nest_y = WORLD_SIZE // 2, WORLD_SIZE // 2
world = World(WORLD_SIZE, (nest_x, nest_y))

world.nest[nest_x-2:nest_x+3, nest_y-2:nest_y+3] = 1
world.food_source[10:20, 50:60] = INITIAL_FOOD

ants = [Ant(world, (nest_x, nest_y)) for _ in range(N_ANTS)]

# =========================
# Visualization
# =========================
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

def render():
    img = np.zeros((WORLD_SIZE, WORLD_SIZE, 3))

    # Food source (green) - decreases as ants take it
    if world.food_source.max() > 0:
        img[..., 1] = np.clip(world.food_source / INITIAL_FOOD, 0, 1)

    # Pheromone trails - blended visualization
    # "To nest" pheromone in RED (shows path from food to nest)
    img[..., 0] = np.clip(world.pheromone_to_nest / 150.0, 0, 1)
    # "To food" pheromone in MAGENTA (red + blue, shows reverse path)
    img[..., 0] += np.clip(world.pheromone_to_food / 150.0, 0, 0.5) * 0.5
    img[..., 2] += np.clip(world.pheromone_to_food / 150.0, 0, 0.5) * 0.5

    # Nest (blue outline)
    img[..., 2] += world.nest * 0.3

    # Food at nest (cyan = blue + green)
    nest_food_intensity = np.clip(world.food_nest / (INITIAL_FOOD * 0.02), 0, 1)
    img[..., 1] += nest_food_intensity * 0.7
    img[..., 2] += nest_food_intensity * 0.7

    # Ants - yellow if carrying food, white if searching
    for ant in ants:
        if ant.carrying_food:
            img[ant.x, ant.y] = [1, 0.8, 0]  # Orange-yellow (carrying food)
        else:
            img[ant.x, ant.y] = [1, 1, 1]  # White (searching)

    return img

# Main visualization
im1 = ax1.imshow(render(), interpolation="nearest")
ax1.set_title(f"Ant Colony (Red=To Nest Trail, Magenta=To Food Trail)", fontsize=12, fontweight='bold')
ax1.axis("off")

# Bar chart showing food distribution
food_remaining = INITIAL_FOOD
food_collected = 0
bars = ax2.barh(['Food Source', 'Nest'], [food_remaining, food_collected], 
                color=['green', 'cyan'])
ax2.set_xlim(0, INITIAL_FOOD * 1.1)
ax2.set_xlabel('Food Units', fontsize=12)
ax2.set_title('Food Distribution', fontsize=14, fontweight='bold')
ax2.grid(axis='x', alpha=0.3)

# Add text annotations
text_source = ax2.text(food_remaining + 10, 0, f'{food_remaining}', 
                       va='center', fontsize=11, fontweight='bold')
text_nest = ax2.text(food_collected + 10, 1, f'{food_collected}', 
                     va='center', fontsize=11, fontweight='bold')

plt.tight_layout()

def update(frame):
    # Update simulation
    for ant in ants:
        ant.step()
    world.diffuse_pheromones()
    
    # Update main visualization
    im1.set_data(render())
    
    # Update bar chart
    food_remaining = world.food_source.sum()
    food_collected = world.total_collected
    
    bars[0].set_width(food_remaining)
    bars[1].set_width(food_collected)
    
    # Update text
    text_source.set_position((food_remaining + 10, 0))
    text_source.set_text(f'{int(food_remaining)}')
    
    text_nest.set_position((food_collected + 10, 1))
    text_nest.set_text(f'{int(food_collected)}')
    
    ax1.set_title(f"Ant Colony - Progress: {int(food_collected)}/{INITIAL_FOOD} ({100*food_collected/INITIAL_FOOD:.1f}%) | Red=To Nest, Magenta=To Food", 
                  fontsize=11, fontweight='bold')
    
    return [im1, bars[0], bars[1], text_source, text_nest]

ani = FuncAnimation(fig, update, interval=30, blit=True)
plt.show()
