import Calibration
from Detector import Detector
from Positioner import *
from Tracker import Tracker
from time import perf_counter
import os
import cv2
from math import floor

dirname = os.path.dirname(__file__)
# vid_path_1 = os.path.join(dirname, "data/videos/output_apart_0.avi")
# vid_path_2 = os.path.join(dirname, "data/videos/output_apart_1.avi")
vid_path_1 = os.path.join(dirname, "data/videos/output_one_person_0.avi")
vid_path_2 = os.path.join(dirname, "data/videos/output_one_person_1.avi")

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


detector = Detector()

camera_1, camera_2 = camera_setup()
calibrated_values = calibrate_cameras()
image_size = calibrated_values["image_size"]

u = 0 * np.ones((3, 1))
stac = 30
a = 1
b = 40
stdm = np.array([[a],[a],[b]])

tracker = Tracker(u, stac, stdm, 0.1)

tracker.add_person("Persoon", np.array([[0], [0], [0], [0], [0], [0]]))

positioner = Positioner(calibrated_values, 0)

# TODO: GUI
# TODO: adding & removing people (tracker.add_person, tracker.rm_person)

start = perf_counter()
dt = None
dt_last = None
while True:
    #   This loop embodies the main workings of this method
    frame_1, frame_2, success = get_frames(camera_1, camera_2, image_size)

    if success:

        # dt calculation
        stop = perf_counter()
        dt = stop - start
        start = stop

        # make tracker prediction
        prediction = tracker.predict(dt)

        #   recognize every person in every frame:
        coordinates_1, coordinates_2 = detector.detect_both_frames(frame_1, frame_2)

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
            while True:
                key = cv2.waitKey(1)
                if key % 256 == 32:
                    #   play
                    print("play")
                    break
        else:
            # this frame needs to be saved and calculated!

            # detect points
            dets = positioner.get_XYZ(coordinates_1, coordinates_2)
            # update filter
            tracked_points = tracker.update(dets)
            
            pers_count = 0
            for pers in tracked_points:
                if dets != []:
                    print("dets:", dets)
                    print("tracked points[pers]:",tracked_points[pers])
                    print("perscount:",pers_count,"change due to kalman filter:\n", dets[0]-tracked_points[pers].T,
                        "\n___________________________________________________________")
                    pers_count+=1
                point_on_img = positioner.reprojectPoint(tracked_points[pers])
                # print on image 1(point_on_img)
                a, b, c, d = int(point_on_img[0][0]), int(point_on_img[0][1]), 10, 10

                if dets != []:
                    color = (0, 255, 210)
                else:
                    color = (255, 0, 210)
                cv2.rectangle(frame_1, (a, b), (a + c, b + d), color, 5)

                # print on image 2(point_on_img)
                a, b, c, d = int(point_on_img[1][0]), int(point_on_img[1][1]), 10, 10

                cv2.rectangle(frame_2, (a, b), (a + c, b + d), color, 5)

            cv2.imshow("Camera one...", frame_1)
            cv2.imshow("Camera two...", frame_2)
            cv2.waitKey(1)

    else:
        print("Frame skipped.")


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
