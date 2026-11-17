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

Python 3 port (2026) of the 2016 "camino" (path) version of the ant
simulation built on top of the template above. Behaviour is intentionally
unchanged; only what no longer works on Python 3 / current libraries was
replaced:
    - gobject.idle_add + GTKAgg      ->  matplotlib.animation.FuncAnimation
    - scipy.copy (removed from SciPy) ->  numpy.copy
    - `from pylab import *`          ->  explicit numpy / matplotlib imports
    - print statements               ->  print() calls, silenced by --quiet
One bug fix: a queen placed within 4 cells of the top or right edge made the
original crash at startup (IndexError); queen squares are now clipped to the
grid.
Added: `--save FILE.gif` renders frames to a file instead of opening a window.

Usage:
    python3 ants_camino.py                       # interactive window
    python3 ants_camino.py --quiet               # same, without console output
    python3 ants_camino.py --save camino.gif     # write an animated GIF
"""
import argparse
import random

import numpy as np
import matplotlib.pyplot as plt
from matplotlib import cm
from matplotlib.animation import FuncAnimation

# pylab's randint was numpy's: the upper bound is exclusive.
# (random.randint, from the standard library, is inclusive; both are used.)
randint = np.random.randint

VERBOSE = True
def log(*args):
    if VERBOSE:
        print(*args)


things = ['resource','ant','queen']
resource = 0
ant = 1
queen = 2

size = len(things)

maxX = 200
maxY = 200

#ui = np.zeros([maxX,maxY])+255

queens = []
for i in range(2):
    queens.append((randint(0,maxX),randint(150,maxY)))# = [[250,250],[250,250],[0,250]]
initialAnts = 400
ants = []

def values(s):
    if(s == 'resource'): return np.uint8(150)
    if(s == 'ant'): return np.uint8(200)
    if(s == 'queen'): return np.uint8(255)

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
        self.actualD[0] = random.randint(-1,1)
        self.actualD[1] = random.randint(-1,1)
        self.count = 0
        self.time = 40
        self.a = [0,0,0]
        self.maxLift = 10
        self.vqueen = 0
        pass

    def move(self):
        #
        self.count += 1
        found, x,y = self.search()
        # there is food, we can eat
        if(found == "resource" and self.a[resource] <= self.maxLift):
            self.eat(x,y)

        if(found == "queen"):
            self.vqueen = 60 # "I've seen the queen"

        if(found == "queen" and self.a[resource] > 0):
            self.release(self.x,self.y)

        # walls
        if(self.x +self.actualD[0] >= maxX):
            self.actualD[0]*=-1+random.randint(-1,1)
        if(self.y +self.actualD[1] >= maxY):
            self.actualD[1]*=-1+random.randint(-1,1)
        if(self.x +self.actualD[0] < 0):
            self.actualD[0]*=-1+random.randint(-1,1)
        if(self.y +self.actualD[1] < 0):
            self.actualD[1]*=-1+random.randint(-1,1)

        if(self.vqueen > 0):
            self.vqueen-=1

        if(self.count >= self.time):
            self.count = 0
            self.actualD = [random.randint(-1,1),random.randint(-1,1)];

        paths[np.clip(self.x,0,maxX-1)][np.clip(self.y,0,maxX-1)]+=1
        #if(self.a[resource]>0 or self.vqueen>0):
            #paths[np.clip(self.x,0,maxX-1)][np.clip(self.y,0,maxX-1)]+=1
            #if(random.random()>0.99):
            #self.follow(10) # only if > param
            #else:
        #else:
        self.follow(5) # unconditionally

        #self.x += self.actualD[0]
        #self.y += self.actualD[1]

    def follow(self,param):
        contour = np.array([
            [self.x,self.y+1],
            [self.x-1,self.y+1],
            [self.x+1,self.y+1],
            [self.x-1,self.y],
            [self.x+1,self.y],
            [self.x-1,self.y-1],
            [self.x,self.y-1],
            [self.x+1,self.y-1],
        ])

        maxx1 = self.x + self.actualD[0]
        maxy1 = self.y + self.actualD[1]
        maxx = maxx1
        maxy = maxy1
        maxv = paths[np.clip(maxx,0,maxX-1),np.clip(maxy,0,maxY-1)]
        if(self.a[resource]>0 or self.vqueen>0):
            log("Prev: ", maxv)
        for i in range(0,len(contour)):
            a = contour[i]
            x1 = np.clip(a[0],0,maxX-1)
            x2 = np.clip(a[1],0,maxY-1)
            w = paths[x1,x2]
            diffx = maxx1 - x1
            diffy = maxy1 - x2
            if(w>maxv and diffx <=1 and diffy<=1 and w > param):
                if(self.a[resource]>0 or self.vqueen>0):
                    log("then: ",w)
                maxv = w
                maxx = x1
                maxy = x2
                self.actualD = [maxx-self.x,maxy-self.y]

        #if(self.a[resource] > 0):

        #if(np.random.random() > 0.01):
        self.x += self.actualD[0]
        self.y += self.actualD[1]

    def eat(self,x,y):
        ui[x][y] = np.uint8(0)
        self.a[resource] += 1
        self.count = self.time
        #self.move()
    def release(self,x,y):
        ui[x][y] = np.uint8(values('queen')) # to make it possible to continue releasing things
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
            #v = 0
            #if(self.tipo == 0):
                #v = self.a[resource]*100 #100#values('ant')/2
            #else:
            v = self.a[resource]*100
            #print v
            ui2[self.x][self.y] = 200

dx=0.01        # Interval size in x-direction.
dy=0.01        # Interval size in y-direction.
a=0.5          # Diffusion constant.
timesteps=5000  # Number of time-steps to evolve system.

nx = maxX#int(1/dx)
ny = maxY#int(1/dy)

dx2=dx**2 # To save CPU cycles, we'll compute Delta x^2
dy2=dy**2 # and Delta y^2 only once and store them.

# For stability, this is the largest interval possible
# for the size of the time-step:
dt = dx2*dy2/( 2*a*(dx2+dy2) )

# Start u and ui off as zero matrices:
ui = np.zeros([nx,ny])
ui2 = np.zeros([nx,ny])
u = np.zeros([nx,ny])
paths = np.zeros([nx,ny]) # importance of paths

# Now, set the initial conditions (ui).
for i in range(nx):
    for j in range(ny):
        ui[i,j] = random.random()*0.00001
        ui2[i,j] = random.random()*0.000001
        paths[i,j] = 0.0#random.random()*0.0001

def updatefig(*args):
    global u, ui, m,ui2,paths
    im.set_array(10*paths+ui+ui2)#ui+ui2)
    if(m%(maxX)==0): paths-=1
    log(paths.sum())
    #ui = sp.copy(u)
    ui2 = np.copy(u)

    log(paths.sum())
    log(ui[0:20][0:20])
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

#for i in range(1,499):
#    for j in range(1,499):
#        ui[i][j] = values('resource')

for i in range(20,40):
    for j in range(20,40):
        ui[i][j] = values('resource')

for i in range(len(queens)):
    x = queens[i][0]
    y = queens[i][1]
    # clipped to the grid (the original could index past the edge and crash)
    for j in range(x-4,min(x+4,nx)):
        for k in range(y-4,min(y+4,ny)):
            ui[j][k] = values('queen')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--save', help='write the animation to this file (.gif) instead of showing it')
    parser.add_argument('--frames', type=int, default=600, help='frames to render with --save')
    parser.add_argument('--quiet', action='store_true', help='no console output')
    args = parser.parse_args()
    VERBOSE = not (args.quiet or args.save)

    if args.save:
        import matplotlib
        matplotlib.use('Agg')

    fig = plt.figure(1)
    img = plt.subplot(111)

    im = img.imshow( 10*paths+ui+ui2, cmap=cm.gray,origin='lower')

    m=1
    fig.colorbar( im ) # Show the colorbar along the side

    if args.save:
        anim = FuncAnimation(fig, updatefig, frames=args.frames, interval=30, blit=False)
        anim.save(args.save, writer='pillow', fps=30)
    else:
        # the original called updatefig whenever the GUI was idle; this is the
        # portable equivalent (cache_frame_data=False: frames are not reusable)
        anim = FuncAnimation(fig, updatefig, interval=1, blit=False, cache_frame_data=False)
        plt.show()
