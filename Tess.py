
from distutils.log import debug
from myPy import im,mything,me

import SimpleITK as sitk



class TessMap(im.Imaginable):
    #override
    def __init__(self, imaginable=None,**kwargs):
        super().__init__(**kwargs)
        if imaginable is not None:
            self.setImaginable(imaginable)

    def __writeToFile__(self,C,V,filename):
        with open(filename, 'w') as f:
            c=0
            for k in C:
                f.write(f'{k[0]} {k[1]} {k[2]} {V[c]}\n')
                c=c+1

    def writeMapToFileAs(self,filename=None,mask=None):
        """Save the pixels values in the map as txt file with coordinates and value
        using the pattern defined un __writeTofile

        Args:
            filename (str, optional): Txt output filename.
            mask (_type_, optional): If a mask is set the output file will contains only the voxels in the map. Defaults to None.

        Returns:
            _type_: Bool
        """        
        return self.writeVoxelsCloudAs(filename,mask)
    
    def setImaginable(self,a=im.Imaginable):
        self.setImage(a.getImage())
        return True
    
    #overrride
    def takeThisImage(self,ima):
        
        if isinstance(ima, str):
            self.setInputFileName(ima)
        elif isinstance(ima,sitk.Image):
            self.setImage(ima)
        elif isinstance(ima,im.Imaginable):
            self.setImaginable(ima)
        elif isinstance(ima,TessMap):
            self=ima
        
        else:
            return False
        return True
    
    

    
    

def findMinMax(ima):
    S=ima.getImageSize()
    M=ima.getImageArray() #zyx numpy
    
    zmin=0
    for c in range(S[2]):
      
      for b in range(S[1]):
        for a in range(S[0]):
          if (M[c, b, a]>0):
            zmin = c
            break
        if (zmin>0):
          break
      if (zmin>0):
        break
    
    zmax=0
    for c in range(S[2]-1, 0, -1):

      for b in range(S[1]):
        for a in range(S[0]):
          if (M[c, b, a]>0):
            zmax = c
            break
        if (zmax>0):
          break
      if(zmax>0):
        break
    print(zmin, zmax)

    return zmin, zmax

import os
import uuid
import copy
class Tess(object):
    
    def __init__(self,workingdirectory=None):
        self.conf={'bin':os.getenv('TESS_BIN','cpptemperature'),'debug':False}
        self.parameters={}
        self.parametersFilename=None
        self.TList=[[]]
        self.Mask=TessMap()
        self.maps={
        'W':TessMap(), #Blood Perfusion,
        'R':TessMap(), #Material Density,
        'C':TessMap(), #Heat Capacity,
        'k':TessMap(), #Thermal Conductivity,
        'Q':TessMap(), #Heat Generated by the metabolism,
        'SAR':TessMap(), #Specific energy Absorption Rate
        'TOld':TessMap(), #TOld
        'Output':TessMap(), #Output
                        }
        self.required={}
        if workingdirectory is None:
            workingdirectory=str(uuid.uuid4())
        self.workingdirectory=workingdirectory

        self.__reset__()
    
    def setDebug(self):
        self.conf["debug"]=True
    
    def setProduction(self):
        self.conf["debug"]=False

    def __reset__(self):
        
        r=self.workingdirectory
        try:
            os.mkdir(r)
        except:
            pass

        self.parameters={
        "Nx" :None, 
        "Ny":None,
        "Nz":None,
        "dx":None,
        "dy":None,
        "dz":None,
        "dt":0.2,
        "zmin":None,
        "zmax":None,
        "maxsavetime":-1,# do not change
        "DeltaSave":10, #s do not change
        "heatingtime":60,#s
        "eps":1e-9, #zero ideal
        "Cblood":1057,
        "Rblood":3600,
        "Tblood":None,
        "Wair":0, #mmL/M*Kg M=minuti
        "Rair":1.3, #Kg/m^3
        "Cair":1006.0, #Joule/(Kg*K)
        "Kair":0.026, #Watt/(m*K)
        "Qair":0, #Watt/kg
        "Tair":None, #K
        "T0V":None,
        "Toldfile":f"{r}/Told.dat", #K
        "SARfile":f"{r}/SAR.dat", #Watt/(kg)
        "Wfile":f"{r}/W.dat",
        "Rfile":f"{r}/R.dat",
        "Qfile":f"{r}/Q.dat",
        "Cfile":f"{r}/C.dat",
        "Kfile":f"{r}/K.dat",
        "outputfile":f"{r}/Toutput.dat",
        "Posxfile":"uniform",
        "Posyfile":"uniform",
        "Poszfile":"uniform",
        "Tbloodfile":"constant", # do not change
        "scaleSARfile":"constant", # do not change scaling factor
        }
        self.parametersFileStatus=False
        self.parametersFilename=f'{r}/Parameters.dat'
        self.maps["Output"]=TessMap()
        self.TList=[[]]
        self.required={"space":False}

    def __setVolumeInfo__(self,ima):
        
        if not self.required["space"]:
            if ima.isImageSet():
                S=ima.getImageSize()
                self.parameters["Nx"] =str(S[0]) 
                self.parameters["Ny"]=str(S[1])
                self.parameters["Nz"]=str(S[2])
                R=ima.getImageSpacing()
                self.parameters["dx"] =str(R[0]/1000)  #it's in meters
                self.parameters["dy"]=str(R[1]/1000) #it's in meters
                self.parameters["dz"]=str(R[2]/1000) #it's in meters
                self.parameters["T0V"]=str(ima.getNumberOfNonZeroVoxels())


    def __readOutput__(self,fn=None):
        if fn is None:
            fn=self.getOutputFilename()
        with open(fn, 'r') as f:
            lines = [line.rstrip('\n') for line in f]
            f.close()
        return lines
    def __createMapFromPointList__(self,lines=[]):
        IM = self.getMask().getDuplicate()
        O=IM.createZerosNumpyImageSameDimensionOfImaginable()
        # read the file
       
        for line in lines:
            x,y,z, value = line.split(" ")
            try:

                O[int(z),int(y),int(x)]=float(value) #numpy is ZYX
            except:
                print("no")
        
        IM.setImageArray(O)
        return IM
    def __writeParamsFile__(self):
        with open(self.getParameterFilename(), 'w') as the_file:
            for key in self.parameters:
                the_file.write(f'{key} = {self.parameters[key]}\n')
        the_file.close()
    def __calculateTemperature__(self):
        b=mything.BashIt()
        b.setCommand(self.conf["bin"] +" "+  self.getParameterFilename())
        print("start")
        b.run()
        print("finished")
        return True

    def getParameterFilename(self):
        return self.parametersFilename

    def setParameterFilename(self,s):
        self.parametersFilename=s

    def getParameterFileStatus(self):
        return self.parametersFileStatus

    def setParameterFileStatus(self,s=True):
        self.parametersFileStatus=s
    
    def __canIStartTheCalculation(self):
        # the parameter file exists
        # the maps file exists
        # all the parameters are set 
        return True

    def setBloodPerfusionOutputFilename(self,filename):
        self.parameters["Wfile"]=filename
    
    def getBloodPerfusionOutputFilename(self):
        return self.parameters["Wfile"]

    def setBloodPerfusionMap(self,filename):
        """set the W term of the bioheat equations

        Args:
            filename ('str,sitk.image,im.Imaginable): a 3d map
        """        
        self.maps["W"].takeThisImage(filename)
        self.__setVolumeInfo__(self.getBloodPerfusionMap())
        self.maps["W"].writeMapToFileAs(self.getBloodPerfusionOutputFilename(),mask=self.getMask())

    def getBloodPerfusionMap(self):
        return self.maps["W"]
        



    def setHeatingTime(self,t):
        self.parameters["heatingtime"]=t

    def getHeatingTime(self):
        return self.parameters["heatingtime"]
    

    def setMask(self,filename):
        """set a Mask

        Args:
            filename ('str,sitk.image,im.Imaginable): a 3d map
        
        """     
        if (self.Mask.takeThisImage(filename)):
            zmin, zmax =findMinMax(self.getMask())
            self.parameters["zmin"]=zmin
            self.parameters["zmax"]=zmax


        return True


    def getMask(self):
        return self.Mask






    def setMaterialDensityOutputFilename(self,filename):
        self.parameters["Rfile"]=filename
    
    def getMaterialDensityOutputFilename(self):
        return self.parameters["Rfile"]

    def setMaterialDensityMap(self,filename):
        """set the R term of the bioheat equations

        Args:
            filename ('str,sitk.image,im.Imaginable): a 3d map
        """        
        self.maps["R"].takeThisImage(filename)
        self.__setVolumeInfo__(self.getMaterialDensityMap())
        self.maps["R"].writeMapToFileAs(self.getMaterialDensityOutputFilename(),mask=self.getMask())

    def getMaterialDensityMap(self):
        return self.maps["R"]

    def setHeatCapacityOutputFilename(self,filename):
        self.parameters["Cfile"]=filename
    
    def getHeatCapacityOutputFilename(self):
        return self.parameters["Cfile"]

    def setHeatCapacityMap(self,filename):
        """set the C term of the bioheat equations

        Args:
            filename ('str,sitk.image,im.Imaginable): a 3d map
        """        
        self.maps["C"].takeThisImage(filename)
        self.__setVolumeInfo__(self.getHeatCapacityMap())
        self.maps["C"].writeMapToFileAs(self.getHeatCapacityOutputFilename(),mask=self.getMask())
    
    def getHeatCapacityMap(self):
        return self.maps["C"]
    
    def setMetabolismHeatOutputFilename(self,filename):
        self.parameters["Qfile"]=filename
    
    def getMetabolismHeatOutputFilename(self):
        return self.parameters["Qfile"]

    def setMetabolismHeatMap(self,filename):
        """set the Q term of the bioheat equations

        Args:
            filename ('str,sitk.image,im.Imaginable): a 3d map
        """        
        self.maps["Q"].takeThisImage(filename)
        self.__setVolumeInfo__(self.getMetabolismHeatMap())
        self.maps["Q"].writeMapToFileAs(self.getMetabolismHeatOutputFilename(),mask=self.getMask())
      
    def getMetabolismHeatMap(self):
        return self.maps["Q"]
   
    def setTermalConductivityOutputFilename(self,filename):
        self.parameters["Kfile"]=filename
    
    def getTermalConductivityOutputFilename(self):
        return self.parameters["Kfile"]

    def setTermalConductivityMap(self,filename):
        """set the k term of the bioheat equations

        Args:
            filename ('str,sitk.image,im.Imaginable): a 3d map
        """        
        self.maps["k"].takeThisImage(filename)
        self.__setVolumeInfo__(self.getTermalConductivityMap())
        self.maps["k"].writeMapToFileAs(self.getTermalConductivityOutputFilename(),mask=self.getMask())

    def getTermalConductivityMap(self):
        return self.maps["k"]

    def setSAROutputFilename(self,filename):
        self.parameters["SARfile"]=filename
    
    def getSAROutputFilename(self,):
        return self.parameters["SARfile"]

    def setSARMap(self,filename):
        """set the SAR term of the bioheat equations

        Args:
            filename ('str,sitk.image,im.Imaginable): a 3d map
        """        
        self.maps["SAR"].takeThisImage(filename)
        self.__setVolumeInfo__(self.getSARMap())
        self.maps["SAR"].writeMapToFileAs(self.getSAROutputFilename(),mask=self.getMask())

    def getSARMap(self):
        return self.maps["SAR"]

    def setTOldOutputFilename(self,filename):
        # I know seems strange but it's like that
        self.parameters["Toldfile"]=filename
    
    def getTOldOutputFilename(self):
        return self.parameters["Toldfile"]

    def setTOldMap(self,filename):
        """set the T Old term of the bioheat equations

        Args:
            filename ('str,sitk.image,im.Imaginable): a 3d map
        """        
        self.maps["TOld"].takeThisImage(filename)
        self.__setVolumeInfo__(self.getTOldMap())
        self.maps["TOld"].writeMapToFileAs(self.getTOldOutputFilename(),mask=self.getMask())

    def getTOldMap(self):
        return self.maps["TOld"]
    def setOutputFilename(self,filename):
        # I know seems strange but it's like that
        self.parameters["outputfile"]=filename
    
    def getOutputFilename(self):
        return self.parameters["outputfile"]
    
    def getOutput(self):
        if self.conf['debug']:
            self.TList=self.__readOutput__('debug/Told.dat')

        else:
            if len(self.TList[0])==0:
                self.__writeParamsFile__()
                if(self.__calculateTemperature__()):
                    self.TList=self.__readOutput__()
        return self.TList     
        

    def getOutputMap(self):
        if (not self.maps["Output"].isImageSet()):
            PVlist=self.getOutput()
            O=self.__createMapFromPointList__(PVlist)
            self.maps["Output"].takeThisImage(O.getImage())
        return self.maps["Output"]
    
    def saveOutputMapAs(self,filename):
        O=self.getOutputMap()
        O.writeImageAs(filename)

    def writeOutputMapAs(self,filename):
        self.saveOutputMapAs(filename)


    def setBloodParameters(self,d):
        # D={'capacity':1057,'density:3600,'temperature':310}
        self.parameters["Cblood"]=d['capacity']
        self.parameters["Rblood"]=d['density']
        self.parameters["Tblood"]=d['temperature']
    
    def getBloodParameters(self):
        # D={'capacity':1057,'density:3600,'temperature':310}
        return {
            'capacity': self.parameters["Cblood"],
            'density':self.parameters["Rblood"],
           'temperature':self.parameters["Tblood"]
        }


    def getTemplatesForWCRTQKParameters(self):

        return self.getAirParameters()

    def setAirParameters(self,d1):
        d= copy.deepcopy(d1)
        self.parameters["Wair"] = d['perfusion']
        self.parameters["Cair"]=d['capacity']
        self.parameters["Rair"]=d['density']
        self.parameters["Tair"]=d['temperature']
        self.parameters["Qair"]=d['metabolism']
        self.parameters["Kair"]=d['conductivity']
    
    def getAirParameters(self):
        d1= {
            'capacity': self.parameters["Cair"],
            'density':self.parameters["Rair"],
           'temperature':self.parameters["Tair"],
           'metabolism':self.parameters["Qair"],
           'conductivity':self.parameters["Kair"],
           'perfusion':self.parameters["Wair"]
        }
        return copy.deepcopy(d1)

    



        






