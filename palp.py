"""
palp is a Python library for automatic label placement.

"""


import numpy as np


from point2d import Point2D


class Label:
    """A Label defines a label to be placed."""

    def __init__(self, optimal=Point2D(), width=0.0, height=0.0, text=''):
        self.optimal = optimal
        self.location = optimal
        self.width = width
        self.height = height
        self.text = text

    def get_rectangle(self):
        """Return the Rectangle of the label."""
        return Rectangle(Point2D(self.location.x - self.width / 2,
                                 self.location.y - self.height / 2),
                         Point2D(self.location.x + self.width / 2,
                                 self.location.y + self.height / 2))


def get_overlap(a, b, c, d):
    """Return overlap between ranges [a, b] and [c, d]."""
    assert a <= b
    assert c <= d
    return max(0, min(b - c, d - a))


# overlap unit tests
assert get_overlap(0, 1, 2, 3) == 0
assert get_overlap(0, 2, 1, 3) == 1


class Rectangle:
    """A Rectangle defines a rectangular region."""

    def __init__(self, bottom_left=Point2D(), top_right=Point2D()):
        self.bottom_left = bottom_left
        self.top_right = top_right

    def overlap_with(self, other):
        """Return the overlap distance with another Rectangle."""
        # get x overlap
        return max(get_overlap(self.bottom_left.x, self.top_right.x,
                               other.bottom_left.x, other.top_right.x),
                   get_overlap(self.bottom_left.y, self.top_right.y,
                               other.bottom_left.y, other.top_right.y))

    def __repr__(self):
        """Return a string representation."""
        args = []
        for attr in dir(self):
            # skip hidden values/functions
            if attr.startswith('_'):
                continue
            # skip all functions
            if callable(getattr(self, attr)):
                continue
            args.append('%s=%s' % (attr, getattr(self, attr)))
        return '%s(%s)' % (self.__class__.__name__, ', '.join(sorted(args)))

# define some labels
labels = []
labels.append(Label(Point2D(1.0, 0.0), 3, 1, 'one'))
labels.append(Label(Point2D(2.0, 0.6), 3, 1, 'two'))
labels.append(Label(Point2D(1.5, 1.0), 5, 1, 'three'))

# define some keepouts
keepouts = []

# keepout and intersection violation penalty factor
penalty = 1.0

# maximum iterations to perform
max_iteration_count = 100

# perturbation distance
delta = 0.01

# get cost if labels are perturbed by the given amount
def get_cost():
    # get cost factor
    cost = 0.0
    # add cost due to distance from optimal location
    for label in labels:
        cost += label.optimal.distance_to(label.location) ** 2
    # add cost due to intersection with other labels
    for i in range(len(labels)):
        one = labels[i].get_rectangle()
        for j in range(i + 1, len(labels)):
            two = labels[j].get_rectangle()
            cost += one.overlap_with(two) ** 2
    return cost


# get cost if labels are perturbed by the given amount
def get_cost_delta(index, amount):

    # get cost factor
    cost = 0.0
    # add cost due to distance from optimal location
    for label in labels:
        cost += label.optimal.distance_to(label.location) ** 2
    # add cost due to intersection with other labels
    for i in range(len(labels)):
        one = labels[i].get_rectangle()
        for j in range(i + 1, len(labels)):
            two = labels[j].get_rectangle()
            cost += one.overlap_with(two) ** 2
    return cost


def get_unknowns(labels):
    """Return the positions of labels into a list."""
    return [x for
            label in labels
            for x in [label.location.x, label.location.y]]


def set_unknowns(labels, unknowns):
    for i in len(labels):
        labels[i].location.x = unknowns[2 * i]
        labels[i].location.y = unknowns[2 * i + 1]


def adjust_unknown(labels, index, amount):
    if index % 2 == 0:
        labels[index // 2].location.x += amount
    if index % 2 == 0:
        labels[index // 2].location.x += amount


def restore_unknown(labels, index, unknowns):
    if index % 2 == 0:
        labels[index // 2].location.x = unknowns[index]
    if index % 2 == 0:
        labels[index // 2].location.x = unknowns[index]


# store solution
for iteration in range(max_iteration_count):
    # get cost factor
    cost = 0.0
    # add cost due to distance from optimal location
    for label in labels:
        cost += label.optimal.distance_to(label.location) ** 2
    distance_cost = cost
    # add cost due to intersection with other labels
    for i in range(len(labels)):
        one = labels[i].get_rectangle()
        for j in range(i + 1, len(labels)):
            two = labels[j].get_rectangle()
            cost += one.overlap_with(two) ** 2
    intersect_cost = cost - distance_cost
    print('\nOn iteration %d:' % iteration)
    print('- Cost=%g (distance=%g, intersect=%g)'
          % (cost, distance_cost, intersect_cost))
    # get dcost/dxi
    dcost = [0.0] * (len(labels) * 2)
    unknowns = get_unknowns(labels)
    for i in range(len(labels) * 2):
        adjust_unknown(labels, i, delta)
        pos_cost = get_cost()
        restore_unknown(labels, i, unknowns)
        adjust_unknown(labels, i, -delta)
        neg_cost = get_cost()
        restore_unknown(labels, i, unknowns)
        dcost[i] = (pos_cost - neg_cost) / (2 * delta)
    # find optimal amount to travel down this path

    # get dcost/dxidxj
    ddcost = [[0.0] * (len(labels) * 2) for _ in range(len(labels) * 2)]
    for i in range(len(labels) * 2):
        for j in range(len(labels) * 2):
            adjust_unknown(labels, i, delta)
            adjust_unknown(labels, j, delta)
            pos_pos_cost = get_cost()
            restore_unknown(labels, i, unknowns)
            restore_unknown(labels, j, unknowns)
            adjust_unknown(labels, i, delta)
            adjust_unknown(labels, j, -delta)
            pos_neg_cost = get_cost()
            restore_unknown(labels, i, unknowns)
            restore_unknown(labels, j, unknowns)
            adjust_unknown(labels, i, -delta)
            adjust_unknown(labels, j, delta)
            neg_pos_cost = get_cost()
            restore_unknown(labels, i, unknowns)
            restore_unknown(labels, j, unknowns)
            adjust_unknown(labels, i, -delta)
            adjust_unknown(labels, j, -delta)
            neg_neg_cost = get_cost()
            restore_unknown(labels, i, unknowns)
            restore_unknown(labels, j, unknowns)
            ddcost[i][j] = 1.0 / (4.0 * delta ** 2)
            ddcost[i][j] *= (pos_pos_cost - pos_neg_cost -
                             neg_pos_cost + neg_neg_cost)
    print(dcost)
    print(ddcost)

    print(np.linalg.eig(ddcost))
    exit(1)
