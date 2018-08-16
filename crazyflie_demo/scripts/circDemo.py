#!/usr/bin/env python

#Drone 1: Forward/backward; (0,-0.6,0.4) <-> (0,0.6,0.4)
#Drone 2: Circle, center(0,0,0.4) radius(0.6). 
#Drone 2 stops + hovers when Drone 1 is near endpoints, (within 0.2?)
import rospy
import tf
from crazyflie_driver.msg import Position
from crazyflie_driver.msg import Hover
from crazyflie_driver.msg import GenericLogData
from std_msgs.msg import Empty
from crazyflie_driver.srv import UpdateParams
from threading import Thread
import math

cf2stop = False
cf1nextInteresect = []
cf1pos = [0,0,0,0]
cf2pos = [0,0,0,0]

def callback_cf1pos(data):
    global cf1pos
    cf1pos[0] = data.values[0]
    cf1pos[1] = data.values[1]
    cf1pos[2] = data.values[2]

def callback_cf2pos(data):
    global cf2pos
    cf2pos[0] = data.values[0]
    cf2pos[1] = data.values[1]
    cf2pos[2] = data.values[2]

class Crazyflie:
    def __init__(self, prefix):
        self.prefix = prefix

        worldFrame = rospy.get_param("~worldFrame", "/world")
        self.rate = rospy.Rate(10)

        rospy.wait_for_service(prefix + '/update_params')
        rospy.loginfo("found update_params service")
        self.update_params = rospy.ServiceProxy(prefix + '/update_params', UpdateParams)

        self.setParam("kalman/resetEstimation", 1)
        self.setParam("flightmode/posSet", 1)

        self.pub = rospy.Publisher(prefix + "/cmd_setpoint", Position, queue_size=1)
        self.msg = Position()
        self.msg.header.seq = 0
        self.msg.header.stamp = rospy.Time.now()
        self.msg.header.frame_id = worldFrame
        self.msg.x = 0
        self.msg.y = 0
        self.msg.z = 0
        self.msg.yaw = 0

        self.stop_pub = rospy.Publisher(prefix + "/cmd_stop", Empty, queue_size=1)
        self.stop_msg = Empty()

    def setParam(self, name, value):
        rospy.set_param(self.prefix + "/" + name, value)
        self.update_params([name])

    def goToSetpoint(self, setpoint):
        self.msg.x = setpoint[0]
        self.msg.y = setpoint[1]
        self.msg.z = setpoint[2]
        self.msg.yaw = setpoint[3]
        self.msg.header.seq += 1
        self.msg.header.stamp = rospy.Time.now()
        self.pub.publish(self.msg)

def dist(v1, v2):
    return abs( (v1[0] - v2[0])**2 + (v1[1]-v2[1])**2 + (v1[2] - v1[2])**2 )**(0.5)

def ylineNext(height, r, step, steps):
    x = 0
    direct = 1
    #step = 0 is intersect1, y=-r
    #step = steps/2 is intersect2, y=+r
    if step > steps/2:
        direct = -1
        step -= steps/2
    y = -r+r*4*step/steps
    y = y*direct
    return [x, y, height, 0], direct
    

def circNext(height, r, step, steps):
    angle = 2*math.pi*step/steps
    x = r*math.cos(angle)
    y = r*math.sin(angle)
    yaw = angle
    return [x, y, height, yaw]

def cf2task(cf):
    global cf2stop, cf1nextInteresect, cf2pos
    rate = rospy.Rate(10)
    cf2pos = [0,0,0,0]
    cf2setpoint = []
    #start setpoint, go to 0,6, 0, 0.4
    cf2setpoint = [0, -0.6, 0.4, 0]
    cf2nextIntersect = [0, 0.6, 0.4, 0]
    #Take off
    #cf.goToSetpoint([0, 0, 0.4, 0])
    radius = 0.6
    currentStep = 0
    divisions = 90
    stay = False
    for i in range(20):
        cf2setpoint = circNext(cf2setpoint[2], radius, currentStep, divisions)
        cf.goToSetpoint(cf2setpoint)
        rate.sleep()
    while(True):
        if (dist(cf2nextIntersect, cf2pos) < 0.1):
            cf2nextIntersect[1] *= -1
        if cf2stop and cf2nextIntersect[1] == cf1nextInteresect[1]:
            d = dist(cf2pos, cf1nextInteresect)
            if (0.1 < d < 0.2):
                stay = True 
        if (stay):
            cf.goToSetpoint(cf2pos) #stay at position
        else:
            cf2setpoint = circNext(cf2setpoint[2], radius, currentStep, divisions)
            currentStep = currentStep + 1
            cf.goToSetpoint(cf2setpoint)
        #CIRCLE
        print("CF2: internal,goal \n" + str(cf2pos) + "," + str(cf2setpoint) )
        rate.sleep()
    return

def cf1task(cf):
    global cf2stop, cf1nextInteresect, cf1pos
    rate = rospy.Rate(10)
    cf1pos = [0,0,0,0]
    #1=>going toward y=0.6, -1=>going toward y=-0.6
    direction = 1
    radius = 0.6
    currentStep = 75
    divisions = 300
    cf1setpoint = ylineNext(height, radius, currentStep, divisions)
    cf1nextInteresect = [0,0.6,0.4,0]
    #take off
    cf.goToSetpoint([0, 0, 0.4, 0])
    while(True):
        cf1setpoint, direction = ylineNext(height, radius, currentStep, divisions)
        currentStep = currentStep + 1 % divisions
        cf.goToSetpoint(cf1setpoint)
        cf1nextInteresect[1] *= direction
        #find out internal position, set cf1pos
        if ( dist(cf1pos, cf1nextInteresect) < 0.2):
            cf2stop = True
        else:
            cf2stop = False
        print("CF1: internal,goal \n" + str(cf1pos) + "," + str(cf1setpoint) )
        rate.sleep()
    return


if __name__ == '__main__':
    rospy.init_node('position', anonymous=True)

    #cf1 = Crazyflie("cf1")
    cf2 = Crazyflie("cf2")
    #rospy.Subscriber("log1", GenericLogData, callback_cf1pos)
    rospy.Subscriber("log2", GenericLogData, callback_cf2pos)
    #t1 = Thread(target=cf1task, args=(cf1,))
    t2 = Thread(target=cf2task, args=(cf2,))
    #t1.start()
    t2.start()
    #t1.join()
    t2.join()



