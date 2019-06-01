from tkinter import *
from tkinter.tix import Tk, Control, ComboBox  #升级的组合控件包
from tkinter.messagebox import showinfo, showwarning, showerror #各种类型的提示框
from PIL import Image, ImageTk

from pykinect2 import PyKinectV2
from pykinect2.PyKinectV2 import *
from pykinect2 import PyKinectRuntime

import cv2 
import numpy as np

from CNN_Train.cnn_model import cnn
from LSTM_Train.lstm_model import lstm

import sys, os

CURR_PATH = os.path.dirname(os.path.abspath(__file__))+"/"

sys.path.append(CURR_PATH + "githubs/tf-pose-estimation")
from tf_pose.networks import get_graph_path, model_wh
from tf_pose.estimator import TfPoseEstimator
from tf_pose import common

from pk_func import draw_body

# Openpose Human pose detection ==============================================================

class SkeletonDetector(object):
    # This func is copied from https://github.com/ildoonet/tf-pose-estimation
    def __init__(self, model=None, image_size=None):
        
        if model is None:
            model = "cmu"

        if image_size is None:
            image_size = "640x480" 

        models = set({"mobilenet_thin", "cmu"})
        self.model = model if model in models else "mobilenet_thin"
        self.resize_out_ratio = 4.0

        w, h = model_wh(image_size)
        if w == 0 or h == 0:
            e = TfPoseEstimator(get_graph_path(self.model),
                                target_size=(432, 368))
        else:
            e = TfPoseEstimator(get_graph_path(self.model), target_size=(w, h))

        self.w, self.h = w, h
        self.e = e

        self.cnt_image = 0

    def detect(self, image):
        self.cnt_image += 1
        if self.cnt_image == 1:
            self.image_h = image.shape[0]
            self.image_w = image.shape[1]
            self.scale_y = 1.0 * self.image_h / self.image_w

        # Inference
        humans = self.e.inference(image, resize_to_default=(self.w > 0 and self.h > 0),
                                #   upsample_size=self.args.resize_out_ratio)
                                  upsample_size=self.resize_out_ratio)


        return humans
    
    def draw(self, img_disp, humans):
        img_disp = TfPoseEstimator.draw_humans(img_disp, humans, imgcopy=False)

    def humans_to_skelsList(self, humans, scale_y = None): # get (x, y * scale_y)
        # type: humans: returned from self.detect()
        # rtype: list[list[]]
        if scale_y is None:
            scale_y = self.scale_y
        skeletons = []
        NaN = 0
        for human in humans:
            skeleton = [NaN]*(18*2)
            for i, body_part in human.body_parts.items(): # iterate dict
                idx = body_part.part_idx
                skeleton[2*idx]=body_part.x
                skeleton[2*idx+1]=body_part.y * scale_y
            skeletons.append(skeleton)
        return skeletons, scale_y

# ==============================================================

class basic_desk():
    def __init__(self,master):
        self.master = master
        
        # 初始化进入界面
        self.basic = Frame(self.master,width=1000,height=1000)
        self.basic.pack()
        # 标题
        Label(self.basic,text='Action Recognition',font=("Arial",15)).pack()
        

        
        self.model_frame = Frame(self.basic)
        self.model_frame.pack()
        # Choose Neural Model
        # Create label
        model_label = Label(self.model_frame,text='The neural model: ')
        model_label.grid(row=1,column=0,rowspan=2,columnspan=2)
        
        self.model_type = StringVar()
        self.model_type.set('LSTM')
        model_LSTM = Radiobutton(self.model_frame,text='LSTM',variable=self.model_type,value='LSTM')
        model_LSTM.grid(row=5,column=1)
        model_CNN = Radiobutton(self.model_frame,text='CNN',variable=self.model_type,value='CNN')
        model_CNN.grid(row=5,column=6)

        self.skeleton_frame = Frame(self.basic)
        self.skeleton_frame.pack()
        # Choose the skeleton algorithm 
        # Create label
        skeleton_label = Label(self.skeleton_frame,text='The skeleton algorithm: ')
        skeleton_label.grid(row=1,column=0,rowspan=2,columnspan=2)
        
        self.skeleton_type = StringVar()
        self.skeleton_type.set('Kinect')
        skeleton_Kinect = Radiobutton(self.skeleton_frame,text='Kinect',variable=self.skeleton_type,value='Kinect')
        skeleton_Kinect.grid(row=5,column=1)
        skeleton_openpose = Radiobutton(self.skeleton_frame,text='OpenPose',variable=self.skeleton_type,value='OpenPose')
        skeleton_openpose.grid(row=5,column=6)

        # 底栏Frame
        self.bottom_frame = Frame(self.master)
        self.bottom_frame.pack(side=BOTTOM,anchor=SW)
        # 进入下一界面
        change = Button(self.bottom_frame,text='Continue',command=self.change_func)
        change.grid(row=1,column=1)
        # 退出
        _quit = Button(self.bottom_frame,text='  Quit  ',command=self.master.quit)
        _quit.grid(row=1,column=2)

    def change_func(self):
        # 进入下一界面
        self.basic.destroy()
        self.detect()
        # self.bottom_frame.destroy()
        # detect_desk(self.master,device=self.device,flag=flag)

    def detect(self):
        # 初始化进入界面
        self.detect_frame = Frame(self.master,width=1000,height=1000)
        self.detect_frame.pack()

        self._kinect = PyKinectRuntime.PyKinectRuntime(PyKinectV2.FrameSourceTypes_Color | PyKinectV2.FrameSourceTypes_Body | PyKinectV2.FrameSourceTypes_Depth)

        # label info
        self.label = StringVar()

        if self.model_type == 'LSTM':
            self.model = lstm
        elif self.model_type =='CNN':
            self.model = cnn
        
        if self.skeleton_type == 'OpenPose':
            self.detector = SkeletonDetector("mobilenet_thin","640x480")

        self.loop()

        # label info2
        action_label = Label(self.detect_frame,textvariable=self.label)
        action_label.pack(side=LEFT)
        
    def loop(self):
        # self.label.set("test")
        try:
            img = self._kinect.get_last_color_frame()
        except:
            success = False
        else:
            img = np.reshape(img,[1080,1920,4])
            self.img = cv2.cvtColor(img,cv2.COLOR_RGBA2RGB)
            success = True

        if success:
            temp_joints = np.array([],dtype=float)
            if self.skeleton_type == 'Kinect':
                if self._kinect.has_new_body_frame(): 
                    self._bodies = self._kinect.get_last_body_frame()
                    for i in range(0, self._kinect.max_body_count):
                        body = self._bodies.bodies[i]
                        if not body.is_tracked: 
                            continue           
                        joints = body.joints 
                        # convert joint coordinates to color space 
                        joint_points = self._kinect.body_joints_to_color_space(joints)
                        draw_body(joints, joint_points,self.img)
                        for i in range(0,25):
                            temp_joints = np.append(temp_joints,joints[i].Position.x)
                            temp_joints = np.append(temp_joints,joints[i].Position.y)
                            temp_joints = np.append(temp_joints,joints[i].Position.z)
            elif self.skeleton_type == 'OpenPose':
                humans = self.detector.detect(self.img)
                skeletons,scale_y = self.detector.humans_to_skelsList(humans)
                self.detector.draw(self.img,humans)
                self._kinect.color_frame_desc
        self.detect_frame.after(1,self.loop)


if __name__ == "__main__":
    # initialize Tk
    root = Tk() 
    root.title("Action Recognition")   
    root.geometry("640x550")    
    root.resizable(width=True, height=True) # 设置窗口是否可以变化长/宽，False不可变，True可变，默认为True
    root.tk.eval('package require Tix')  #引入升级包

    basic_desk(root)

    root.mainloop()