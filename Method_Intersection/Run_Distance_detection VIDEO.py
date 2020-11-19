import Calibration
from Detector import Detector
from Positioner_new import *
from Positioner import *
from Tracker import Tracker
from time import perf_counter
import os
import cv2
import matplotlib.pyplot as plt
from math import floor

dirname = os.path.dirname(__file__)

#vid_path_1 = os.path.join(dirname, "data/videos/output_two_person_0.avi")
#vid_path_2 = os.path.join(dirname, "data/videos/output_two_person_1.avi")
vid_path_1 = os.path.join(dirname, "data/videos/output_two_person_0.avi")
vid_path_2 = os.path.join(dirname, "data/videos/output_two_person_1.avi")
timestamps_path = os.path.join(dirname, "data/timestamps/output_two_person_timestamps.txt")

CALIB_PATH = os.path.join(dirname, "data/calib.pckl")

# THIS VERSION REPLACES CAMERA STREAM WITH VIDEO STREAM

def camera_setup():
    # k = 4 #int(input("enter a scaledown factor:\n"))
    cv2.namedWindow("Camera one...")
    cv2.namedWindow("Camera two...")
    camera_1 = cv2.VideoCapture(vid_path_1)
    camera_2 = cv2.VideoCapture(vid_path_2)
    #   getting the right resolution:
    # camera_1.set(cv2.CAP_PROP_FRAME_WIDTH, floor(1920 / k))
    # camera_2.set(cv2.CAP_PROP_FRAME_WIDTH, floor(1920 / k))
    # camera_1.set(cv2.CAP_PROP_FRAME_HEIGHT, floor(1080 / k))
    # camera_2.set(cv2.CAP_PROP_FRAME_HEIGHT, floor(1080 / k))

    ret_cal_1, frame_cal_1 = camera_1.read()
    if not ret_cal_1:
        print("failed to grab frame_1")
    ret_cal_2, frame_cal_2 = camera_2.read()
    if not ret_cal_2:
        print("failed to grab frame_1")
    cv2.imshow("Camera one...", frame_cal_1)
    cv2.imshow("Camera two...", frame_cal_2)
    #   are the cameras reversed?
    reversed = bool(
        1  # int(input("Enter 1 if the cameras are reversed. Enter 0 if they are right"))
    )
    if reversed:
        camera_1, camera_2 = camera_2, camera_1
    return camera_1, camera_2


def calibrate_cameras():
    calibrate = (
        False  # (input("Do you want to calibrate the camera? (1:Yes, 0:No):\n"))
    )
    if calibrate:
        #   CALIBRATION
        #   calibrated_values = (fov, dir_1, dir_2, coord_1, coord_2)
        calibrated_values = Calibration.calculate(camera_1, camera_2)
        Calibration.save_calibration(CALIB_PATH, calibrated_values)
    else:
        calibrated_values = Calibration.load_calibration(CALIB_PATH)

    return calibrated_values


def get_frames(camera_1, camera_2, size):
    ret_1, frame_1 = camera_1.read()
    if not ret_1:
        print("failed to grab frame_1")
        return None, None, False

    ret_2, frame_2 = camera_2.read()
    if not ret_2:
        print("failed to grab frame_2")
        return None, None, False

    frame_1 = cv2.resize(frame_1, size)
    frame_2 = cv2.resize(frame_2, size)

    return frame_1, frame_2, True

def extract_timestamps():
    f = open(timestamps_path, "r")
    lines = f.read().split("\n")
    timestamps = {}
    for line in lines:
        split = line.split(",")
        timestamps[int(split[0])] = split[1:]
    
    return timestamps


detector = Detector()
camera_1, camera_2 = camera_setup()

calibrated_values = calibrate_cameras()
image_size = calibrated_values["image_size"]


u = 0 * np.ones((3, 1))
stac = 1
stdm = np.array([[0.1],[0.1],[1]])
tracker = Tracker(u, stac, stdm, 0.1)

start_R = [[5], [5], [1], [0], [0], [0]]
start_L = [[0], [5], [1], [0], [0], [0]]

positioner = Positioner2(calibrated_values, 0.0027)

timestamps = extract_timestamps()

# TODO: GUI
# TODO: adding & removing people (tracker.add_person, tracker.rm_person)

start = perf_counter()
dt = None
dt_last = None

# frame count
n = 0

while True:
    # cv2.waitKey()

    #   This loop embodies the main workings of this method
    frame_1, frame_2, success = get_frames(camera_1, camera_2, image_size)

    if success:
        n += 1
        event = timestamps.get(n, None)
        if event is not None:
            if event[1] == "Exit":
                tracker.rm_person(event[0])

            elif event[1] == "Enter":
                if event[2] == "R":
                    tracker.add_person(event[0], start_R)
                elif event[2] == "L":
                    tracker.add_person(event[0], start_L)

        # dt calculation
        #stop = perf_counter()
        #dt = stop - start
        #start = stop
        dt = 0.1

        # make tracker prediction
        prediction = tracker.predict(dt)

        #   recognize every person in every frame:
        coordinates_1, coordinates_2, boxes_1, boxes_2 = detector.detect_both_frames(frame_1, frame_2)

        key = cv2.waitKey(1)

        # TODO: replace with GUI functions
        if key % 256 == 27:
            # ESC pressed
            print("Escape hit, closing...")
            cv2.destroyAllWindows()
            break

        elif key % 256 == 32:
            #   space pressed:
            #       pause right now, changes being made to code
            print("paused, press space to continue")
            print("debug time!")
            while True:
                key = cv2.waitKey(1)
                if key % 256 == 32:
                    #   play
                    print("play")
                    break
        else:
            # this frame needs to be saved and calculated!

            # detect points
            dets = positioner.get_XYZ(coordinates_1, coordinates_2, prediction)
            print("OMFG3", dets)
            # update filter
            tracked_points = tracker.update(dets)

            for pers in tracked_points:
                #if dets != []:
                    #print(
                    #    "change due to kalman filter:\n",
                    #    dets[0] - tracked_points[pers].T,
                    #    "\n___________________________________________________________",
                    #)
                point_on_img = positioner.reprojectPoint(tracked_points[pers])
                # print on image 1(point_on_img)
                a, b, c, d = int(point_on_img[0][0]), int(point_on_img[0][1]), 20, 20

                cv2.rectangle(frame_1, (a - c, b - d), (a + c, b + d), (255, 0, 210), 5)

                # print on image 2(point_on_img)
                a, b, c, d = int(point_on_img[1][0]), int(point_on_img[1][1]), 20, 20

                cv2.rectangle(frame_2, (a - c, b - d), (a + c, b + d), (255, 0, 210), 5)

            # Plot boxes
            for box in boxes_1:
                cv2.rectangle(frame_1, (box[0], box[1]) , (box[2], box[3]), (50,50,200))
            for box in boxes_2:
                cv2.rectangle(frame_2, (box[0], box[1]) , (box[2], box[3]), (50,50,200))

            # Plot dets
            for det in dets:
                point_on_img = positioner.reprojectPoint(np.array([det]).T)
                a, b, c, d = int(point_on_img[0][0]), int(point_on_img[0][1]), 1, 1
                cv2.rectangle(frame_1, (a, b), (a + c, b + d), (255, 150, 100), 5)
                a, b, c, d = int(point_on_img[1][0]), int(point_on_img[1][1]), 1, 1
                cv2.rectangle(frame_2, (a, b), (a + c, b + d), (255, 150, 100), 5)

            cv2.imshow("Camera one...", frame_1)
            cv2.imshow("Camera two...", frame_2)
            cv2.waitKey(1)

    else:
        print("Frame skipped.")


# output: dictionary { "naam": ( [[x],[y],[z]], [x, y], [x, y], [x1, y1, x2, y2], [x1, y1, x2, y2]), ...etc... } , 
# output: dictionary { "naam": ([3D positie], [2D punt op linkse foto], [2D punt op rechtse foto], [bounding box op linkse foto], [bounding box op rechtse foto]) }



# TODO: display this in the GUI
# for (x, y, w, h) in faces:
#             cv2.rectangle(image, (x, y), (x + w, y + h), (0, 255, 0), 2)
#             a = (w // 2) - 3
#             b = (w // 2) + 3
#             c = x + a
#             d = y + a
#             cv2.rectangle(image, (c, d), (c + 6, d + 6), (0, 100, 250), 2)
#         #   display in the right window
#         if one_or_two == 1:
#             cv2.imshow("Recognition one...", image)
#         else:
#             cv2.imshow("Recognition two...", image)
