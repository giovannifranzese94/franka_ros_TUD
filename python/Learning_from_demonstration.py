#%%
#!/usr/bin/env python
from winreg import REG_EXPAND_SZ
import rospy
import math
import numpy as np
import time

from zmq import RECONNECT_IVL_MAX
from sensor_msgs.msg import JointState
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import Float32MultiArray, Float32
import dynamic_reconfigure.client
from sys import exit
from pynput.keyboard import Listener, KeyCode

class LfD():
    def __init__(self):
        rospy.init_node('LfD', anonymous=True)
        self.r=rospy.Rate(10)
        self.curr_pos=None
        self.width=None
        self.recorded_traj = None 
        self.recorded_gripper= None

        self.pos_sub=rospy.Subscriber("/cartesian_pose", PoseStamped, self.ee_pos_callback)
        self.gripper_sub=rospy.Subscriber("/joint_states", JointState, self.gripper_callback)
        self.joints=rospy.Subscriber("/joint_states", JointState, self.joint_callback)  
        self.goal_pub = rospy.Publisher('/equilibrium_pose', PoseStamped, queue_size=0)
        self.joint_pub = rospy.Publisher('/equilibrium_configuration', JointState , queue_size=0)
        self.grip_pub = rospy.Publisher('/gripper_online', Float32, queue_size=0)
        self.stiff_mat_pub_ = rospy.Publisher('/stiffness', Float32MultiArray, queue_size=0) #TODO check the name of this topic 
        #self.stiff_diag_pub = rospy.Publisher('/stiffness', , queue_size=0) #TODO check the name of this topic 
        self.listener = Listener(on_press=self._on_press)
        self.listener.start()
    def _on_press(self, key):
        # This function runs on the background and checks if a keyboard key was pressed
        if key == KeyCode.from_char('e'):
            self.end = True        
        if key == KeyCode.from_char('j'):
            self.save_joint_position = True  
        if key == KeyCode.from_char('c'):
            self.save_cartesian_position = True    
    def ee_pos_callback(self, data):
        self.curr_pos = np.array([data.pose.position.x, data.pose.position.y, data.pose.position.z])
        self.curr_ori = np.array([data.pose.orietation.x, data.pose.orietation.y, data.pose.orietation.z, data.pose.orietation.w])
        #rospy.loginfo([data.x, data.y, data.z])
    def gripper_callback(self, data):
        self.width =data.position[7]+data.position[8]
        #rospy.loginfo(self.width)
    def joint_callback(self,data):
        self.curr_joint =data.position[0:7]

    def set_stiffness(k_t1, k_t2, k_t3,k_r1,k_r2,k_r3, k_ns):

        set_K = dynamic_reconfigure.client.Client('/dynamic_reconfigure_compliance_param_node', config_callback=None)
        set_K.update_configuration({"translational_stiffness_X": k_t1})
        set_K.update_configuration({"translational_stiffness_Y": k_t2})
        set_K.update_configuration({"translational_stiffness_Z": k_t3})        
        set_K.update_configuration({"rotational_stiffness_X": k_r1}) 
        set_K.update_configuration({"rotational_stiffness_Y": k_r2}) 
        set_K.update_configuration({"rotational_stiffness_Z": k_r3})
        set_K.update_configuration({"nullspace_stiffness": k_ns}) 

    def record_point(self):
        #stiff_des = Float32MultiArray()
        #stiff_des.data = np.array([0.0, 0.0, 0.0, 30.0, 30.0, 30.0, 20.0]).astype(np.float32)
        #self.stiff_pub.publish(stiff_des) 

        self.recorded_cartesian = self.curr_pos
        self.recorded_orientation = self.curr_ori
        self.recorded_joint = self.curr_joint
        self.recorded_gripper= self.width

        while self.end ==False:       
            if  self.save_joint_position==True: 
                self.recorded_joint = np.c_[self.recorded_joint, self.curr_joint]
                self.recorded_gripper = np.c_[self.recorded_gripper, self.width]
                print('Adding joint cartesian position')
                time.sleep(0.5) 
                self.save_joint_position==False

            if  self.save_cartesian_position==True: 
                self.recorded_cartesian = np.c_[self.recorded_cartesian, self.curr_pos]
                self.recorded_orientation = np.c_[self.recorded_orientation, self.curr_ori]
                self.recorded_gripper = np.c_[self.recorded_gripper, self.width]
                print('Adding cartesian position') 
                time.sleep(0.5)
                self.save_cartesian_position==False     

            self.r.sleep()
  
    def traj_rec(self):
        # trigger for starting the recording
        trigger = 0.05
        # print("test pt 1")
       # stiff_des = Float32MultiArray()
       # stiff_des.data = np.array([0.0, 0.0, 0.0, 30.0, 30.0, 30.0, 20.0]).astype(np.float32)
        #self.stiff_pub.publish(stiff_des) 

        init_pos = self.curr_pos
        init_ori = self.curr_ori
        vel = 0
        vel_ori=0
        while not(vel > trigger or vel_ori> trigger):
            vel     = math.sqrt((self.curr_pos[0]-init_pos[0])**2 + (self.curr_pos[1]-init_pos[1])**2 + (self.curr_pos[2]-init_pos[2])**2)
            vel_ori = math.sqrt((self.curr_ori[0]-init_ori[0])**2 + (self.curr_ori[1]-init_ori[1])**2 + (self.curr_ori[2]-init_ori[2])**2)
        self.recorded_traj = self.curr_pos
        self.recorded_ori = self.curr_ori
        self.recorded_joints = self.curr_joint
        self.recorded_gripper= self.width
        # recorded_joint = joint_pos
        key_pressed = False
        while not key_pressed:
            now = time.time()      

            self.recorded_traj = np.c_[self.recorded_traj, self.curr_pos]
            self.recorded_ori = np.c_[self.recorded_ori, self.curr_ori]
            self.recorded_gripper = np.c_[self.recorded_gripper, self.width]
            self.recorded_joint = np.c_[self.recorded_joints, self.curr_joint]


            self.r.sleep()

    # control robot to desired goal position
    def go_to_start_cart(self):
        start = self.curr_pos
        start_ori = self.curr_ori
        goal_=np.array([self.recorded_traj[0][0], self.recorded_traj[1][0], self.recorded_traj[2][0]])#TODO Check this
        print("goal:", goal_)
        goal_ori_=np.array([self.recorded_ori[0][0], self.recorded_ori[1][0], self.recorded_ori[2][0], self.recorded_ori[3][0]])
        print("goal_ori:", goal_ori_)
        # interpolate from start to goal with attractor distance of approx 1 cm
        squared_dist = np.sum(np.subtract(start, goal_)**2, axis=0)
        dist = np.sqrt(squared_dist)
        print("dist", dist)
        interp_dist = 0.01  # [m]
        step_num = math.floor(dist / interp_dist)
        print("num of steps", step_num)
        x = np.linspace(start[0], goal_[0], step_num)
        y = np.linspace(start[1], goal_[1], step_num)
        z = np.linspace(start[2], goal_[2], step_num)
        rot_x= np.linspace(start_ori[0], goal_ori_[0], step_num)
        rot_y= np.linspace(start_ori[1], goal_ori_[1], step_num)
        rot_z= np.linspace(start_ori[2], goal_ori_[2], step_num)
        rot_w= np.linspace(start_ori[3], goal_ori_[3], step_num)

        goal = PoseStamped()
        goal.pose.position.x = x[0]
        goal.pose.position.y = y[0]
        goal.pose.position.z = z[0]

        goal.pose.orientation.x = rot_x[0]
        goal.pose.orientation.y = rot_y[0]
        goal.pose.orientation.z = rot_z[0]
        goal.pose.orientation.w = rot_w[0]

        self.goal_pub.publish(goal)


        goal = PoseStamped()
        for i in range(step_num):
            now = time.time()            # get the time
            goal.header.seq = 1
            goal.header.stamp = rospy.Time.now()
            goal.header.frame_id = "map"

            goal.pose.position.x = x[i]
            goal.pose.position.y = y[i]
            goal.pose.position.z = z[i]

            goal.pose.orientation.x = rot_x[i]
            goal.pose.orientation.y = rot_y[i]
            goal.pose.orientation.z = rot_z[i]
            goal.pose.orientation.w = rot_w[i]
            self.goal_pub.publish(goal)
            self.r.sleep()   

    def execute_cart_points(self):
        for i in range (self.recorded_traj.shape[1]):
            goal = PoseStamped()

            goal.header.seq = 1
            goal.header.stamp = rospy.Time.now()
            goal.header.frame_id = "map"

            goal.pose.position.x = self.recorded_traj[0][i] 
            goal.pose.position.y = self.recorded_traj[1][i]
            goal.pose.position.z = self.recorded_traj[2][i]

            goal.pose.orientation.x = self.recorded_ori[0][i]
            goal.pose.orientation.y = self.recorded_ori[1][i]
            goal.pose.orientation.z = self.recorded_ori[2][i]
            goal.pose.orientation.w = self.recorded_ori[3][i]

            self.goal_pub.publish(goal)
            
            grip_command = Float32()

            grip_command.data = self.recorded_gripper[0][i]

            self.grip_pub.publish(grip_command) 

            time.sleep(3)            

    #def start_ros(self):
#%%    
LfD=LfD()

#%%
        #LfD.start_ros()
#%%
input("Press Enter to start trajectory recording...")
LfD.traj_rec()  # a new window should open for stopping the recording

#%%
LfD.go_to_start()

#%%
        LfD.execute()
#%%
