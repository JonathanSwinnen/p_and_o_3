# Positioner.py rewrite
# NOTE: NIET GETEST!!! Ik heb GEEN idee of die recursieve functie werkt of niet


from munkres import Munkres
import numpy as np
import munkres
from numpy.lib.type_check import imag


class Positioner2:
    def __init__(self, calibration_values, pairing_range):
        """Creates a new Positioner instance

        Parameters
        ----------
        calibration_values : dict
            Dictionary containing calibration values. create this with Calibration.py
        pairing_range : float
            maximum projection error to consider a left and right point combination as a possible pairing
        """
        self.calibration_values = calibration_values
        self.pairing_range = pairing_range
        d = 0.5
        self.M = [
            (d * self.calibration_values["dir_1"] + self.calibration_values["coord_1"]),
            (d * self.calibration_values["dir_2"] + self.calibration_values["coord_2"]),
        ]
        self.x_vector = [self.calibration_values["x1"], self.calibration_values["x2"]]
        self.y_vector = [self.calibration_values["y1"], self.calibration_values["y2"]]
        self.M_afbeelding = np.array(
            [
                self.calibration_values["image_size"][0] / 2,
                self.calibration_values["image_size"][1] / 2,
            ]
        )

    # TODO: Implement 3D formules

    def pixel_to_image_plane(self, pixel, camera):
        """
        converts a pixel coordinate (x,y) to a 3D point, on the right image plane
        Args:   -pixel (x,y)
                -camera: 1 or 2
        Returns:
                coordinate XYZ of the pixel on the right image plane
        """
        P = (
            self.M[camera - 1]
            + (pixel[0] - self.M_afbeelding[0]) * self.x_vector[camera - 1]
            + (pixel[1] - self.M_afbeelding[1]) * self.y_vector[camera - 1]
        )
        return P

    def intersection_line_with_imageplane(
        self, line_point_1, line_point_2, image_plane
    ):
        """
        Calculates the intersection of a line with an imageplane
        Args:
            - line_direction: np.array([dirx,diry,dirz]) of said line
            - line_point: a known point on said line
            - image plane: either 1 or 2
        Returns:
            - the XYZ coordinates of the intersectionpoint
        """
        line_direction = line_point_2 - line_point_1
        A = np.array(
            [
                [
                    line_direction[0],
                    self.x_vector[image_plane - 1][0],
                    self.y_vector[image_plane - 1][0],
                ],
                [
                    line_direction[1],
                    self.x_vector[image_plane - 1][1],
                    self.y_vector[image_plane - 1][1],
                ],
                [
                    line_direction[2],
                    self.x_vector[image_plane - 1][2],
                    self.y_vector[image_plane - 1][2],
                ],
            ]
        )
        b = self.M[image_plane - 1] - line_point_1
        solution = np.linalg.solve(A, b)
        point = solution[0] * line_direction + line_point_1
        return point

    def distance_point_line(self, point_of_line_1, point_of_line_2, point):
        """
        simple formula to determine the distance between a point and a line through two other points
        """
        distance = np.linalg.norm(
            np.cross(point_of_line_1 - point, point_of_line_2 - point_of_line_1)
        ) / np.linalg.norm(point_of_line_2 - point_of_line_1)

        return distance

    def intersection_lines_of_sight(self, P1, P2):
        Line_1 = P1 - self.calibration_values["coord_1"]
        Line_2 = P2 - self.calibration_values["coord_2"]
        A = np.array(
            [
                [-Line_1[0], Line_2[0]],
                [-Line_1[1], Line_2[1]],
                [-Line_1[2], Line_2[2]],
            ]
        )
        b = self.calibration_values["coord_1"] - self.calibration_values["coord_2"]
        solution_4 = np.linalg.lstsq(A, b, rcond=-1)

        return solution_4[0][0] * Line_1 + self.calibration_values["coord_1"]

    def get_single_3d_point(self, point_camera_1, point_camera_2):
        P1 = self.pixel_to_image_plane(point_camera_1, 1)
        P2 = self.pixel_to_image_plane(point_camera_2, 2)
        intersection = self.intersection_lines_of_sight(P1, P2)
        print("3D POINT CALC: input: ", point_camera_1, point_camera_2, "output ", intersection, sep=",")

        return intersection

    def get_all_3d_points_with_pairing(
        self, points_camera_1, points_camera_2, pairings
    ):
        """returns a list of 3D points calculated from points on two cameras, given a pairing configuration

        Parameters
        ----------
        points_camera_1 : list
            a list of points from camera 1
        points_camera_2 : list
            a list of points from camera 2
        pairings : list
            a list filled with tuples (index_1, index_2) containing index pairs that pair points in points_camera_1 to those in points_camera_2,
            meaning they are both projections of the same 3D point in space
        Returns
        -------
        list
            a list with the calculated 3D points
        """
        dets = []
        # loop over all pairs
        for pair in pairings:
            # add 3D point calculated from pair of 2D projected points
            dets.append(
                self.get_single_3d_point(
                    points_camera_1[pair[0]], points_camera_2[pair[1]]
                )
            )
        return dets

    def get_d(self, point_1, point_2, target_camera):
        """
        returns the distance of the projected line of sight of one point on the image plane of the other camera, to the other point...

        Args:
            - point_1: detected point on camera 1 image
            - point_2: detected point on camera 2 image
            - target_camera: what camera's image to project to (either 0 (means camera 1) or 1)
        Returns:
            distance
        """
        #   detection points on the image planes in 3D:
        P1 = self.pixel_to_image_plane(point_1, 1)
        P2 = self.pixel_to_image_plane(point_2, 2)

        points = [P1, P2]
        cameras = [
            self.calibration_values["coord_1"],
            self.calibration_values["coord_2"],
        ]

        #   calculate two intersections with the target imageplane
        IP1 = self.intersection_line_with_imageplane(cameras[target_camera],
            points[-target_camera - 1],
            target_camera+1)
        
        IP2 = self.intersection_line_with_imageplane(cameras[target_camera],
            cameras[-target_camera-1],
            target_camera+1)
        

        distance = self.distance_point_line(IP1, IP2, points[target_camera])

        return distance

    def get_XYZ(self, points_camera_1, points_camera_2, predictions):
        """Estimates the best guess for XYZ points from detected points on camera 1 and 2, based on a prediction. Detections that yield a big
        reprojection error are omitted, which means that there might sometimes be less estimated 3D points than expected.

        Parameters
        ----------
        points_camera_1 : list
            a list of points from camera 1
        points_camera_2 : list
            a list of points from camera 2
        predictions : list
            list of prediction points

        Returns
        -------
        list
            a list containing the best estimation of detected 3D points
        """

        possible_pairings = []

        # loop over all points and build a list that for every index corresponding to a point in points_camera_1
        # contains another list of indices of possible pairings from points_camera_2
        for point_camera_1 in points_camera_1:

            # best pairings for this point
            possible_pairings.append([])
            i = 0
            for point_camera_2 in points_camera_2:

                # calculate distance between projected points and projected C1P1 and C2P1 for both images = d1 and d2
                d1, d2 = self.get_d(point_camera_1, point_camera_2, 1), self.get_d(
                    point_camera_1, point_camera_2, 0
                )  # TODO: implement

                cost = (
                    d1 * d1 + d2 * d2
                )  # define the cost as the sum of squared distances to the projected lines
                print(cost)
                # points that give a cost below the threshold are possible pairs
                if cost <= self.pairing_range:
                    possible_pairings[-1].append(i)

                i += 1

        # get best point combinations and retrieve 3D points
        _, best_dets = self.get_best_dets_recursively(
            possible_pairings, points_camera_1, points_camera_2, predictions
        )
        print("HOLAPOLA", best_dets)
        return best_dets

    # NOTE: This function is UNTESTED and MIGHT BE UTTER GARBAGE !!!!
    # NOTE: Debugging this will be fun :D /s
    def get_best_dets_recursively(
        self,
        pairings_to_choose,
        points_camera_1,
        points_camera_2,
        predictions,
        current_pairing_index_1=0,
        chosen_pairings=[],
    ):
        """Recursively finds the best 3D point detections, given a set of pairings to choose from

        Parameters
        ----------
        pairings_to_choose : list
            every element of this list is a nested list which corresponds to an entry in points_camera_1 with the same index.
            This nested list contains the indices of points from points_camer_2 that can be paired with the entry from points_camera_1
            example: pairings_to_choose = [[2,3],[1]] means that points_camera_1[0] can be paired with either points_camera_2[2] or [3],
            and that points_camera_1[2] can only be paired with points_camera_2[1]
        points_camera_1 : list
            a list of points from camera 1
        points_camera_2 : list
            a list of points from camera 2
        predictions : list
            list of prediction points
        current_pairing_index_1 : int, optional
            current index to look for pairing options, used for recursion, by default 0
        chosen_pairings : list, optional
            currently chosen pairings, used for recursion, by default []

        Returns
        -------
        list
            best 3D point detections from given pairing options
        """

        # skip leading empty entries
        while (
            current_pairing_index_1 < len(pairings_to_choose)
            and len(pairings_to_choose[current_pairing_index_1]) == 0
        ):
            current_pairing_index_1 += 1

        # no more pairings to choose => calculate and return cost & dets
        if len(pairings_to_choose[current_pairing_index_1:]) == 0:
            # get 3D points from chosen pairings
            dets = self.get_all_3d_points_with_pairing(
                points_camera_1, points_camera_2, chosen_pairings
            )
            # get cost from 3D points
            cost = self.get_mean_dets_vs_prediction_cost(dets, predictions)
            print("pairings: ", chosen_pairings, cost)
            return cost, dets

        # loop over all pairing possibilities i for current index of points_camera_1 to get minimum cost
        min_cost = None
        best_dets = None
        for i in pairings_to_choose[current_pairing_index_1]:
            # new chosen pairings
            new_chosen_pairings = list(chosen_pairings)  # copy
            new_chosen_pairings.append((current_pairing_index_1, i))  # add this pair
            # new next pairings to choose -> move to next entry
            new_pairings_to_choose = list(pairings_to_choose)
            # remove duplicates of i from other pairing possibilities, so no camera point can be used twice, !!! CAN LEAD TO SKIPPED POINTS
            for next_pairing in new_pairings_to_choose:
                if i in next_pairing:
                    next_pairing.remove(i)
            # recursion -> get dets from best pairing sequence after this one
            cost, dets = self.get_best_dets_recursively(
                new_pairings_to_choose,
                points_camera_1,
                points_camera_2,
                predictions,
                current_pairing_index_1 + 1,
                new_chosen_pairings,
            )
            # if this pairing & best next pairing together are optimal, set new best dets & cost
            if cost is not None and (min_cost is None or cost < min_cost):
                print("GOTCHA")
                min_cost = cost
                best_dets = dets

        # return dets from best pairing sequence
        print("YEES", best_dets)
        return min_cost, best_dets

    def get_mean_dets_vs_prediction_cost(self, dets, predictions):
        """returns the minimal mean cost of the distance between a given list of detected 3D points and a prediction
        through the hungarian method.

        Parameters
        ----------
        dets : list
            a list of detected 3D points
        predictions : list
            a list of predictions for the 3D points

        Returns
        -------
        float
            the minimal cost
        """
        if len(dets) == 0 or len(predictions) == 0:
            return None

        # implementation of Hungarian method
        m = Munkres()

        # i = person index, j = det index
        i, j = 0, 0
        # create cost matrix
        cost_matrix_dim = max(len(predictions), len(dets))
        cost_matrix = np.zeros((cost_matrix_dim, cost_matrix_dim))
        print(cost_matrix)
        # loop over all predictions
        for pred_id in predictions:
            prediction_pos = predictions[pred_id]
            j = 0
            # loop over all detections
            for det_pos in dets:
                # add cost matrix entry: distance between prediction point and detection point
                cost_matrix[i][j] = np.linalg.norm(
                    np.array(prediction_pos) - np.array(det_pos).T
                )
                j += 1
            i += 1
        # compute Hungarian algorithm
        
        indices = m.compute(np.copy(cost_matrix))
        # calculate final cost
        cost = 0
        # loop over all best matches
        for (p_num, det_num) in indices:
            if p_num < len(predictions) and det_num < len(dets):
                # add match cost to total
                cost += cost_matrix[p_num][det_num]
        cost /= len(indices)
        return cost


    def get_XYZ_old(
        self,
        points_camera_1,
        points_camera_2,
    ):
        """Determines the XYZ point of the given point seen by two camera's

        Notes:
            - function receives, works with, and returns values in [meter]
            - camera one is positioned above the axis origin
            - direction camera1,camera2 is the direction of the x-axis
            - y axis is pointed lateral to x, in the direction the cameras are looking at
            - z axis is pointed up

        Args:
            self.calibration_values["image_size"]: Size of the images (#pixels x, #pixels y)
            fov: field of view of the camera (horizontally)
            point_camera_1 /2 : the pixel on the images where the point is seen
            self.calibration_values["coord_1"] and self.calibration_values["coord_2"]: positions of cameras
            self.calibration_values["dir_1"] and self.calibration_values["dir_2"]: direction of cameras

        Returns:
            the calculated XYZ points, in a list of np.arrays
        """

        XYZ_POINTS = []
        #   center point of plane:
        d = 0.5
        M1 = self.calibration_values["dir_1"] + d * self.calibration_values["coord_1"]
        #   now we can determine the location of the recognized point in space (P1)
        #       first, determine the middle of the image:

        #   thus, we need a mathematical representation of the second 'imagescreen' plane bv2
        #   we know where the camera faces (self.calibration_values["dir_2"]) and distance d
        M2 = self.calibration_values["coord_2"] + d * self.calibration_values["dir_2"]

        # TODO: optimise: delete already calculated points

        for afb_pos_1 in points_camera_1:
            #   determine line between coord_1 and point on projected image plane 1 (point that has to be calculated)
            #   projected image plane 1
            P1 = self.pixel_to_image_plane(afb_pos_1, 1)

            #   by knowing two points of the projection of line C1P1 on the second image, we can determine the line completely:
            #                   intersection of C1C2 and the plane bv2
            #                   and of P1C2 and the plane bv2
            #   To find the intersections, two linear systems need to be computed
            C1C2 = (
                self.calibration_values["coord_2"] - self.calibration_values["coord_1"]
            )
            P1C2 = self.calibration_values["coord_2"] - P1
            IP1 = self.intersection_line_with_imageplane(
                C1C2, self.calibration_values["coord_1"], 2
            )
            IP2 = self.intersection_line_with_imageplane(P1C2, P1, 2)

            Line_of_sight_1 = IP2 - IP1
            Line_of_sight_1_norm = np.linalg.norm(
                Line_of_sight_1
            )  #    (normalizing the vector)
            Line_of_sight_1 = Line_of_sight_1 / Line_of_sight_1_norm

            #   Now we know where the line-of-sight of camera1 towards said person is,
            #       we need to find the closest recognized point on camera two's image
            #       the intersection of the line between this point and self.calibration_values["coord_2"] and the first line C1P1 is the XYZ point!

            #   P2 is the point of the person in camera2's image
            #   for every detected point on image_2: find the distance, and determine which is most likely to be the right one
            distance = None
            closest_position = None
            shortest_distance = None

            for recognized_pos_2 in points_camera_2:
                P2 = self.pixel_to_image_plane(recognized_pos_2, 2)
                #   find distance of P2 to Line_of_Sight_1
                distance = self.distance_point_line(IP1, IP2, P2)
                if (
                    not shortest_distance or distance <= shortest_distance
                ):  # - self.uncertainty_range
                    shortest_distance = distance
                    closest_position = recognized_pos_2

            # closest match is found: closest_position
            P2 = self.pixel_to_image_plane(closest_position, 2)

            XYZ_POINTS += [(self.intersection_lines_of_sight(P1, P2))]

        return XYZ_POINTS

    def reprojectPoint(self, xyz):
        # TODO: vervang deze placeholder code met projectie

        xyz = np.array([xyz[0][0], xyz[1][0], xyz[2][0]])
        # xyz = np.array([xyz[0][0], xyz[1][0], 1.50])

        # Center of each image plane: (at distance d from the sensor)
        d = 0.5
        M1 = self.calibration_values["coord_1"] + d * self.calibration_values["dir_1"]

        M2 = self.calibration_values["coord_2"] + d * self.calibration_values["dir_2"]

        Line_sight_1 = xyz - self.calibration_values["coord_1"]
        Line_sight_2 = xyz - self.calibration_values["coord_2"]
        # Calculate intersection of the line from xyz to each image sensor with the image planes:
        # print([
        # [
        # Line_sight_1[0],
        # self.calibration_values["x1"][0],
        # self.calibration_values["y1"][0],
        # ],
        # [
        # Line_sight_1[1],
        # self.calibration_values["x1"][1],
        # self.calibration_values["y1"][1],
        # ],
        # [
        # Line_sight_1[2],
        # self.calibration_values["x1"][2],
        # self.calibration_values["y1"][2],
        # ]
        # ])
        A1 = np.array(
            [
                [
                    Line_sight_1[0],
                    self.calibration_values["x1"][0],
                    self.calibration_values["y1"][0],
                ],
                [
                    Line_sight_1[1],
                    self.calibration_values["x1"][1],
                    self.calibration_values["y1"][1],
                ],
                [
                    Line_sight_1[2],
                    self.calibration_values["x1"][2],
                    self.calibration_values["y1"][2],
                ],
            ]
        )

        A2 = np.array(
            [
                [
                    Line_sight_2[0],
                    self.calibration_values["x2"][0],
                    self.calibration_values["y2"][0],
                ],
                [
                    Line_sight_2[1],
                    self.calibration_values["x2"][1],
                    self.calibration_values["y2"][1],
                ],
                [
                    Line_sight_2[2],
                    self.calibration_values["x2"][2],
                    self.calibration_values["y2"][2],
                ],
            ]
        )

        b1 = xyz - M1
        b2 = xyz - M2

        solution_1 = np.linalg.solve(A1, b1)

        solution_2 = np.linalg.solve(A2, b2)

        middle_pixel = (
            self.calibration_values["image_size"][0] // 2,
            self.calibration_values["image_size"][1] // 2,
        )
        XY1 = (middle_pixel[0] + solution_1[1], middle_pixel[1] + solution_1[2])
        XY2 = (middle_pixel[0] + solution_2[1], middle_pixel[1] + solution_2[2])

        return (XY1, XY2)
