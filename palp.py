"""
palp is a Python library for automatic label placement.

"""

import math
import copy

import PySimpleGUI as sg

from point2d import Point2D


class Layout:
    """A Layout contains all placement information."""

    # penalty factor on intersecting labels
    penalty_intersection = 1000.0

    # penalty factor on keepout zones
    penalty_keepout = 1000000.0

    # perturbation distance when getting gradient
    delta = 1e-8

    def __init__(self):
        # list of labels
        self.labels = []
        # list of keeputs
        self.keepouts = []
        # for now, just create some labels and keepouts
        self.labels.append(Label(Point2D(1.0, 0.0), 3, 1, 'one'))
        self.labels.append(Label(Point2D(2.0, 0.6), 3, 1, 'two'))
        self.labels.append(Label(Point2D(1.5, 1.0), 5, 1, 'three'))
        self.labels.append(Label(Point2D(-1, -1.0), 2, 2, 'four'))
        # add a keeopouts
        self.keepouts.append(Label(Point2D(-0.2, 0.5), 0.6, 0.6))

    def get_bounds(self):
        """Return the problem bounds as a Rectangle."""
        rectangles = [label.get_rectangle() for label in self.labels]
        rectangles.extend(keepout.get_rectangle() for keepout in self.keepouts)
        if not rectangles:
            return Rectangle()
        while len(rectangles) >= 2:
            rectangles[0] = Rectangle.get_bound(rectangles[0], rectangles[1])
            del rectangles[1]
        return rectangles[0]

    def draw(self):
        """Draw the system on a popup."""
        # dimensions of the graph element
        graph_size = [800, 600]
        # get bounds to draw
        bounds = self.get_bounds()
        scale_x = bounds.get_width() / graph_size[0]
        scale_y = bounds.get_height() / graph_size[1]
        if scale_x > scale_y:
            new_height = bounds.get_height() * scale_x / scale_y
            added = (new_height - bounds.get_height()) / 2.0
            bounds.bottom_left.y -= added
            bounds.top_right.y += added
        else:
            new_width = bounds.get_width() * scale_y / scale_x
            added = (new_width - bounds.get_width()) / 2.0
            bounds.bottom_left.x -= added
            bounds.top_right.x += added
        # add 10% margin all around
        added = bounds.get_width() / 20.0
        bounds.bottom_left.x -= added
        bounds.top_right.x += added
        added = bounds.get_height() / 20.0
        bounds.bottom_left.y -= added
        bounds.top_right.y += added
        graph = sg.Graph(graph_size,
                         [bounds.bottom_left.x, bounds.bottom_left.y],
                         [bounds.top_right.x, bounds.top_right.y])
        layout = [[graph],
                  [sg.OK(), sg.Cancel()]]
        # print('problem bounds are %s' % bounds)
        window = sg.Window('Label placement').Layout(layout).Finalize()
        # draw labels
        for label in self.labels:
            rect = label.get_rectangle()
            # draw outline
            graph.DrawRectangle([rect.bottom_left.x, rect.top_right.y],
                                [rect.top_right.x, rect.bottom_left.y],
                                None,
                                'black')
            # draw distance from optimal
            graph.DrawLine([label.location.x, label.location.y],
                           [label.optimal.x, label.optimal.y],
                           'blue')
            # draw optimal distance
            graph.DrawCircle([label.optimal.x, label.optimal.y],
                             5.0,
                             None,
                             'blue')
        # draw keepouts
        for keepout in self.keepouts:
            rect = keepout.get_rectangle()
            graph.DrawRectangle([rect.bottom_left.x, rect.top_right.y],
                                [rect.top_right.x, rect.bottom_left.y],
                                None,
                                'red')
        window.Read()

    def get_cost(self, verbose=False):
        """Return the current placement cost."""
        # get cost factor
        cost = 0.0
        # add cost due to distance from optimal location
        for label in self.labels:
            cost += label.optimal.distance_to(label.location) ** 2
        # add cost due to intersection with other labels
        for i in range(len(self.labels)):
            one = self.labels[i].get_rectangle()
            for j in range(i + 1, len(self.labels)):
                two = self.labels[j].get_rectangle()
                this_dist = one.overlap_with(two)
                if verbose and this_dist:
                    print('- overlap between %d and %d by %g'
                          % (i, j, this_dist))
                cost += self.penalty_intersection * this_dist ** 2
        # add cost due to intersection with keepouts
        for i in range(len(self.labels)):
            one = self.labels[i].get_rectangle()
            for j in range(len(self.keepouts)):
                two = self.keepouts[j].get_rectangle()
                this_dist = one.overlap_with(two)
                cost += self.penalty_keepout * this_dist ** 2
                if verbose and this_dist:
                    print('- keepout violation on %d and %d by %g'
                          % (i, j, this_dist))
        return cost

    def get_unknowns(self):
        """Return the positions of labels into a list."""
        return [x for
                label in self.labels
                for x in [label.location.x, label.location.y]]

    def adjust_unknown(self, index, amount):
        if index % 2 == 0:
            self.labels[index // 2].location.x += amount
        else:
            self.labels[index // 2].location.y += amount

    def restore_unknown(self, index, unknowns):
        if index % 2 == 0:
            self.labels[index // 2].location.x = unknowns[index]
        else:
            self.labels[index // 2].location.y = unknowns[index]

    def anneal(self):
        """Perform the annealing operation."""
        # get length scale (maximum dimension)
        length_scale = 1.0
        # minimum distance to move
        min_movement = 1e-6
        # maximum distance to move a label per iteration
        max_movement = 0.1
        # maximum iterations
        max_iteration_count = 100
        # last movement amount
        movement = max_movement
        # movement amount cutback
        movement_cutback = 0.5
        # number of unknowns
        unknown_count = len(self.labels) * 2
        # store directions of steepest descent for each iteration
        descent_vectors = []
        for iteration in range(max_iteration_count):
            print('\nOn iteration %d:' % iteration)
            # get current cost
            cost = self.get_cost(verbose=True)
            # print('- Cost=%g (distance=%g, intersect=%g)'
            #       % (cost, distance_cost, intersect_cost))
            # get dcost/dxi
            dcost = [0.0] * (len(self.labels) * 2)
            unknowns = self.get_unknowns()
            for i in range(len(self.labels) * 2):
                self.adjust_unknown(i, self.delta)
                pos_cost = self.get_cost()
                self.restore_unknown(i, unknowns)
                self.adjust_unknown(i, -self.delta)
                neg_cost = self.get_cost()
                self.restore_unknown(i, unknowns)
                dcost[i] = (pos_cost - neg_cost) / (2 * self.delta)
            # turn dcost into a unit vector
            starting_cost = cost
            dcost_norm = math.sqrt(sum(x * x for x in dcost))
            if dcost_norm == 0.0:
                print('WARNING: Reached local minimum')
                break
            print(dcost)
            dcost = [-x / dcost_norm for x in dcost]
            # save path
            descent_vectors.append(dcost)
            # get tangency
            tangency = 0.0
            if len(descent_vectors) >= 2:
                tangency = sum(x * y
                               for x, y
                               in zip(descent_vectors[-2], descent_vectors[-1]))
                print('- tangency=%g' % tangency)
            if iteration > 0 and tangency < 0.9:
                movement *= movement_cutback
                print('- cutback due to tangency')
            if tangency > 0.95:
                movement *= 2.0
                movement = min(movement, max_movement)
            print('- dphi = %s' % dcost)
            while True:
                # move this much
                for i in range(len(unknowns)):
                    self.adjust_unknown(i, movement * dcost[i])
                new_cost = self.get_cost()
                # if new cost is higher, cutback
                if new_cost >= starting_cost:
                    movement *= movement_cutback
                    print('- cutback due to increased cost')
                    for i in range(len(unknowns)):
                        self.restore_unknown(i, unknowns)
                    if movement <= min_movement:
                        movement = 0.0
                        break
                    continue
                break
            print('- moved by %g' % movement)
            if movement <= min_movement:
                print('minimum movement after %d iterations' % iteration)
                break
            #self.draw()


class Label:
    """A Label defines a label to be placed."""

    def __init__(self, optimal=Point2D(), width=0.0, height=0.0, text=''):
        self.optimal = optimal
        self.location = copy.copy(optimal)
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
assert get_overlap(0.0, 10.0, 8.0, 10.0) == 2.0
assert get_overlap(0.0, 10.0, 8.0, 14.0) == 2.0
assert get_overlap(0.0, 10.0, 2.0, 8.0) == 8.0


class Rectangle:
    """A Rectangle defines a rectangular region."""

    def __init__(self, bottom_left=Point2D(), top_right=Point2D()):
        self.bottom_left = bottom_left
        self.top_right = top_right

    def overlap_with(self, other):
        """Return the overlap distance with another Rectangle."""
        # get x overlap
        return min(get_overlap(self.bottom_left.x, self.top_right.x,
                               other.bottom_left.x, other.top_right.x),
                   get_overlap(self.bottom_left.y, self.top_right.y,
                               other.bottom_left.y, other.top_right.y))

    def is_empty(self):
        """Return True if the Rectangle is empty."""
        return (self.bottom_left.x >= self.top_right.x or
                self.bottom_left.y >= self.top_right.y)

    def get_width(self):
        """Return the width."""
        return max(0, self.top_right.x - self.bottom_left.x)

    def get_height(self):
        """Return the width."""
        return max(0, self.top_right.y - self.bottom_left.y)

    @staticmethod
    def get_bound(one, two):
        """Return a Rectangle that contains both input rectangles."""
        if one.is_empty():
            return copy.copy(two)
        elif two.is_empty():
            return copy.copy(one)
        bound = copy.copy(one)
        bound.bottom_left.x = min(bound.bottom_left.x, two.bottom_left.x)
        bound.bottom_left.y = min(bound.bottom_left.y, two.bottom_left.y)
        bound.top_right.x = max(bound.top_right.x, two.top_right.x)
        bound.top_right.y = max(bound.top_right.y, two.top_right.y)
        return bound

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


problem = Layout()
#problem.draw()
problem.anneal()

print('\n\n\n')
problem.get_cost(verbose=True)
problem.draw()
