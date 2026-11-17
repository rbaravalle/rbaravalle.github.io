#!/usr/bin/env python3
"""
Author: Timothy A.V. Teatro <http://www.timteatro.net>
Date  : Oct 25, 2010
Lisence: Creative Commons BY-SA
(http://creativecommons.org/licenses/by-sa/2.0/)

Description:
    A program which uses an explicit finite difference
    scheme to solve the diffusion equation with fixed
    boundary values and a given initial value for the
    density u(x,y,t). This version uses a numpy
    expression which is evaluated in C, so the
    computation time is greatly reduced over plain
    Python code.

    This version also uses matplotlib to create an
    animation of the time evolution of the density.

Python 3 port (2026) of the original ant simulation built on top of the
template above. The behaviour is intentionally unchanged; only what no longer
works on Python 3 / current libraries was replaced:
    - gobject.idle_add + GTK3Agg  ->  matplotlib.animation.FuncAnimation
                                      (works with any matplotlib backend)
    - scipy.copy (removed from SciPy) ->  numpy.copy
    - `from pylab import *`          ->  explicit numpy / matplotlib imports
    - maxX/2 (a float in Python 3)   ->  maxX//2
Added: `--save FILE.gif` renders frames to a file instead of opening a window.

Usage:
    python3 ants.py                      # interactive window
    python3 ants.py --save ants.gif      # write an animated GIF (needs pillow)
"""
import argparse
import random

import numpy as np
import matplotlib.pyplot as plt
from matplotlib import cm
from matplotlib.animation import FuncAnimation

# pylab's randint was numpy's: the upper bound is exclusive.
randint = np.random.randint


things = ['resource','ant','queen']
resource = 0
ant = 1
queen = 2

size = len(things)

maxX = 500
maxY = 500

#ui = np.zeros([maxX,maxY])+255

queens = []
for i in range(100):
    queens.append((randint(maxX//2-10,maxX//2),randint(10,maxY-10)))# = [[250,250],[250,250],[0,250]]
initialAnts = 1000
ants = []

def values(s):
    if(s == 'resource'): return np.uint8(150)
    if(s == 'ant'): return np.uint8(200)
    if(s == 'queen'): return 100#np.uint8(255)

class Ant():
    def __init__(self,t):
        self.arr = np.zeros((size)).astype(np.float32)
        self.tipo = t
        self.x = randint(0,maxX)
        self.y = randint(0,maxY)
        self.queen = [maxX,maxY]
        self.queen[0] = queens[self.tipo][0]
        self.queen[1] = queens[self.tipo][1]
        self.actualD = [1,1]
        self.actualD[0] = randint(-1,2)
        self.actualD[1] = randint(-1,2)
        self.count = 0
        self.time = 50
        self.a = [0,0,0]
        self.maxLift = 40
        pass

    def move(self):
        #
        if(self.count < self.time):
            self.count += 1
            found, x,y = self.search()
            # there is food, we can eat
            if(found == "resource" and self.a[resource] <= self.maxLift):
                self.eat(x,y)

            if(found == "queen" and self.a[resource] > 0):
                self.release(self.x,self.y)
              # move
            if(self.x +self.actualD[0] >= maxX):
                self.actualD[0]*=-1
            if(self.y +self.actualD[1] >= maxY):
                self.actualD[1]*=-1
            if(self.x +self.actualD[0] < 0):
                self.actualD[0]*=-1
            if(self.y +self.actualD[1] < 0):
                self.actualD[1]*=-1
            self.x += self.actualD[0]
            self.y += self.actualD[1]
        else:
            self.count = 0
            self.actualD[0] = randint(-1,2)
            self.actualD[1] = randint(-1,2)

        #print self.actualD

    def eat(self,x,y):
        ui[x][y] = np.uint8(0)
        self.a[resource] += 1
        self.count = self.time
        self.move()
    def release(self,x,y):
        ui[x][y] = values('queen') # to make it possible to continue releasing things
        self.a[resource] -= 1
        self.count = self.time
        self.move()

    def search(self):
        if(self.x-1 >= 0 and self.x-1 < maxX and self.y >= 0 and self.y < maxY):
            if(ui[self.x-1][self.y] == values('resource')):
                return "resource",self.x-1,self.y
            if(ui[self.x-1][self.y] == values('queen')):
                return "queen",self.x-1,self.y
        if(self.y-1 >= 0 and self.y-1 < maxY and self.x >= 0 and self.x < maxX):
            if(ui[self.x][self.y-1] == values('resource')):
                return "resource",self.x,self.y-1
            if(ui[self.x][self.y-1] == values('queen')):
                return "queen",self.x,self.y-1
        if(self.y+1 < maxY  and self.y+1 < maxY and self.x >= 0 and self.x < maxX):
            #print self.x, self.y+1
            if(ui[self.x][self.y+1] == values('resource')):
                return "resource",self.x,self.y+1
            if(ui[self.x][self.y+1] == values('queen')):
                return "queen",self.x,self.y+1
        if(self.x+1 < maxX  and self.x+1 >= 0 and self.y >= 0 and self.y < maxY):
            if(ui[self.x+1][self.y] == values('resource')):
                return "resource",self.x+1,self.y
            if(ui[self.x+1][self.y] == values('queen')):
                return "queen",self.x+1,self.y
        return False, -1, -1

    def draw(self):
        if(self.x >= 0 and self.x < maxX and self.y >= 0 and self.y < maxY):
            v = 0
            if(self.tipo == 0):
                v = self.a[resource]*100 #100#values('ant')/2
            else: v = self.a[resource]*100
            ui2[self.x][self.y] = v

dx=0.01        # Interval size in x-direction.
dy=0.01        # Interval size in y-direction.
a=0.5          # Diffusion constant.
timesteps=5000  # Number of time-steps to evolve system.

nx = 500#int(1/dx)
ny = 500#int(1/dy)

dx2=dx**2 # To save CPU cycles, we'll compute Delta x^2
dy2=dy**2 # and Delta y^2 only once and store them.

# For stability, this is the largest interval possible
# for the size of the time-step:
dt = dx2*dy2/( 2*a*(dx2+dy2) )

# Start u and ui off as zero matrices:
ui = np.zeros([nx,ny])
ui2 = np.zeros([nx,ny])
u = np.zeros([nx,ny])

# Now, set the initial conditions (ui).
for i in range(nx):
    for j in range(ny):
        ui[i,j] = random.random()*0.0000001
        ui2[i,j] = random.random()*0.0000001

def updatefig(*args):
    global u, ui, m,ui2
    im.set_array(ui+ui2)
    #ui = sp.copy(u)
    ui2 = np.copy(u)


    for i in range(len(ants)):
        ants[i].move()
        ants[i].draw()

    m+=1
    #print "Computing and rendering u for m =", m
    #if m >= timesteps:
    #    return False
    return [im]


for i in range(initialAnts):
    ants.append(Ant(randint(0,2)))

for i in range(1,499):
    for j in range(1,499):
        ui[i][j] = values('resource')

for i in range(20,200):
    for j in range(20,200):
        ui[i][j] = values('resource')

for i in range(len(queens)):
    x = queens[i][0]
    y = queens[i][1]
    r = randint(0,10)
    for j in range(x-r,x+r):
        for k in range(y-r,y+r):
            ui[j][k] = values('queen')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--save', help='write the animation to this file (.gif) instead of showing it')
    parser.add_argument('--frames', type=int, default=300, help='frames to render with --save')
    args = parser.parse_args()

    if args.save:
        import matplotlib
        matplotlib.use('Agg')

    fig = plt.figure(1)
    img = plt.subplot(111)
    im = img.imshow( ui, cmap=cm.gray,origin='lower')

    m=1
    #fig.colorbar( im ) # Show the colorbar along the side

    if args.save:
        anim = FuncAnimation(fig, updatefig, frames=args.frames, interval=30, blit=False)
        anim.save(args.save, writer='pillow', fps=30)
    else:
        # the original called updatefig whenever the GUI was idle; this is the
        # portable equivalent (cache_frame_data=False: frames are not reusable)
        anim = FuncAnimation(fig, updatefig, interval=1, blit=False, cache_frame_data=False)
        plt.show()
