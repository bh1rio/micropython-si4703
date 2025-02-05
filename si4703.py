import time

class Radio:
    # 定义寄存器的名字
    REG_DEVICEID =       0x00
    REG_CHIPID =         0x01
    REG_POWERCFG =       0x02
    REG_CHANNEL =        0x03
    REG_SYSCONFIG1 =     0x04
    REG_SYSCONFIG2 =     0x05
    REG_SYSCONFIG3 =     0x06
    REG_TEST1 =          0x07
    REG_TEST2 =          0x08 #保留寄存器，如果修改最好先读再写。
    REG_BOOTCONFIG =     0x09 #保留寄存器，如果修改最好先读再写。
    REG_STATUSRSSI =     0x0A
    REG_READCHAN =       0x0B
    REG_RDSA =           0x0C
    REG_RDSB =           0x0D
    REG_RDSC =           0x0E
    REG_RDSD =           0x0F

    # 寄存器 0x02 - POWERCFG
    SI4703_SMUTE =          15
    SI4703_DMUTE =          14
    SI4703_SKMODE =         10
    SI4703_SEEKUP =         9
    SI4703_SEEK =           8
    SI4703_DISABLE =        6
    SI4703_ENABLE =         0

    # 寄存器 0x03 - CHANNEL
    SI4703_TUNE =           15

    # 寄存器 0x04 - SYSCONFIG1
    SI4703_RDSIEN =         15
    SI4703_STCIEN =         14
    SI4703_RDS =            12
    SI4703_DE =             11
    SI4703_AGCD =           10
    SI4703_BLNDADJ =        6
    SI4703_GPIO3 =          4
    SI4703_GPIO2 =          2
    SI4703_GPIO1 =          0

    # 寄存器 0x05 - SYSCONFIG2
    SI4703_SEEKTH =         8
    SI4703_SPACE1 =         5
    SI4703_SPACE0 =         4
    SI4703_VOLUME_MASK =    0x000F

    # 寄存器 0x06 - SYSCONFIG3
    SI4703_SKSNR =          4
    SI4703_SKCNT =          0

    # 寄存器 0x07 - TEST1
    SI4703_AHIZEN =         14
    SI4703_XOSCEN =         15

    # 寄存器 0x0A - STATUSRSSI
    SI4703_RDSR =           15
    SI4703_STC =            14
    SI4703_SFBL =           13
    SI4703_AFCRL =          12
    SI4703_RDSS =           11
    SI4703_STEREO =         8

    # 寄存器 0x0B - READCHAN
    SI4703_READCHAN_MASK =  0x03FF    

    # RDS变量
    # 寄存器 RDSB
    SI4703_GROUPTYPE_OFFST = 11
    SI4703_TP_OFFST =       10
    SI4703_TA_OFFST =       4
    SI4703_MS_OFFST =       3
    SI4703_TYPE0_INDEX_MASK = 0x0003
    SI4703_TYPE2_INDEX_MASK = 0x000F

    SI4703_SEEK_DOWN =      0
    SI4703_SEEK_UP =        1
    
    def __init__(this,i2c,rstPin):
        this.i2c=i2c            # 允许i2c共享，但是si4703不支持超过400k的i2c时钟
        this.address=0x10
        this.resetPin=rstPin
        
        this.registers = [0] * 16
        this.rds_ps = [0] * 8
        this.rds_rt = [0] * 64
    
    def ReadRegisters(this):
        # 虽然si4703 datasheet上说其有16个寄存器，每个寄存器2byte大小。
        # 但是这16个寄存器的内容只能一次性读取，不支持分别读取，而且后4个RDS相关寄存器排在了最前面。
        

        # 预制16个2byte寄存器的buffer
        i2cReadBytes = [0] * 32
        
        # 一次性读取32个byte到buffer
        i2cReadBytes = this.i2c.readfrom(this.address, 32)
        
        # 先将0x0A开始的前4个RDS寄存器从buffer取出，接下来再从buffer取0x00开始的12个寄存器。
        regIndex = 0x0A
        for i in range(0,16):
            this.registers[regIndex] = (i2cReadBytes[i*2] * 256) + i2cReadBytes[(i*2)+1]
            regIndex += 1
            if regIndex == 0x10:
                regIndex = 0
                
    def WriteRegisters(this):
        # 写操作自动从0x02寄存器开始，不需要发送寄存器地址。
        # 由于前2个设备信息寄存器、后面8个寄存器：2个保留寄存器，2个只读状态寄存器以及后4个RDS寄存器，都是只读寄存器不需要写入，
        # 所以写入时一次性写入6个寄存器的内容
        
        i2cWriteBytes = [0] * 12
        WriteBuffer = bytearray(12)

        for i in range(0,6):
            # 将2byte的寄存器内容切成2个byte
            i2cWriteBytes[i*2], i2cWriteBytes[(i*2)+1] = divmod(this.registers[i+2], 0x100)

        for i in range(0,12):
            WriteBuffer[i] = i2cWriteBytes[i]
        
        this.i2c.writeto(this.address, WriteBuffer)

    def Init(this):
        # 要使用si4703的两线模式，需要SEN置高，SDA置低，然后重启si4703。
        # 由于市场常见si4703模块都已经对SEN做了拉高，而SDA开始传输前为低，因此对si4703上电的初始化，需要先做一次重启。
        # 如果不先做重启操作，初始化i2c以后，无法扫描到i2c上的si4703设备。
        # 如需自行设计电路，需要注意相关引脚使用上拉电阻拉高。

        # 按照datasheet说明，将RST引脚置低，保持100ms以后，再置高。此时再在i2c上扫描，就能扫描到0x10设备。
        this.resetPin.off()
        time.sleep_ms(100)
        this.resetPin.on()

        # 在重启后，si4703开始工作前，其寄存器已经可以开始读写。
        this.ReadRegisters()
        # 根据datasheet在si4703开始工作前，需要对使用的晶振进行设定。
        # 目前市场常见的si4703模块，都是使用外置32k晶振。
        # 根据datasheet要求，设置晶振以后，需要等待晶振稳定。
        this.registers[this.REG_TEST1] |= (1<<this.SI4703_XOSCEN)
        this.WriteRegisters() # 全部寄存器内容写回。
        time.sleep(0.5) # 等待晶振稳定，此处等待0.5s。

        this.ReadRegisters() #全部寄存器读取
        this.registers[this.REG_POWERCFG] |= (1<<this.SI4703_DMUTE)  # 取消静音
        this.registers[this.REG_POWERCFG] |= (1<<this.SI4703_ENABLE) # 使si4703开始工作

        #this.registers[this.SI4703_SYSCONFIG1] |= (1<<this.SI4703_RDS) # 开启RDS，由于RDS部分尚未完成，暂未开启RDS部分
        this.registers[this.REG_SYSCONFIG1] |= (1<<this.SI4703_DE) # 国标加重为50kHz
        this.registers[this.REG_SYSCONFIG2] |= (1<<this.SI4703_SPACE0) # 国标频道间隔100KHz
        this.registers[this.REG_SYSCONFIG2] &= 0xFFF0 # 清除音量设置
        this.registers[this.REG_SYSCONFIG2] |= 0x0001 # 设置最小音量
        this.WriteRegisters() # 全部寄存器内容写回。
        
        time.sleep(.11) # 启动需要一段时间，根据datasheet等待0.11s

    def ShutDown(this):
        # 根据datasheet描述，关闭si4703需要0x02寄存器的ENABLE位和DISABLE位同时置1
        this.ReadRegisters()
        this.registers[this.REG_POWERCFG] |= (1<<this.SI4703_ENABLE)
        this.registers[this.REG_POWERCFG] |= (1<<this.SI4703_DISABLE)
        this.WriteRegisters() # Update
        
    def printInfo(this):
        this.ReadRegisters()
        pn,mfgid=divmod(this.registers[this.REG_DEVICEID],0x1000)
        rev,other=divmod(this.registers[this.REG_CHIPID],0b10000000000)
        dev,firmware=divmod(other,0b1000000)
        if pn==0x1 and mfgid==0x242:
            print('Silicon Laboratories Si4700/01/02/03')
        if dev==0x9: print('Si4703')
        if dev==0x8: print('Si4701')
        if dev==0x1: print('Si4702')
        if dev==0x0: print('Si4700')
        
        version=''
        if rev==0x2: version+='B'
        if rev==0x3: version+='C'
        version+=str(firmware)
        print(version)
        
    def SetChannel(this,channel):
        # channel变量为从0开始的正整型，为欲设置频率值乘10,如97.4MHz,需要传入974。
        # 0x05寄存器的[7:6]为波段位，默认00表示87.5-108MHz的欧美FM频段。
        # 0x03寄存器的[9:0]为频道位，储存的是频道间隔的个数。
        # 所以需要将channel值减去FM频段的起始值乘10,例如：974-875
        newChannel = channel - 875 # e.g. 973 - 875 = 98
        this.ReadRegisters()
        this.registers[this.REG_CHANNEL] &= 0xFE00 # 先清空[9:0]
        this.registers[this.REG_CHANNEL] |= newChannel; # 设置新值
        this.registers[this.REG_CHANNEL] |= (1<<this.SI4703_TUNE); # 设置TUNE位
        this.WriteRegisters()

        # 由于未使用si4703的GPIO做调谐完成中断引脚，所以需要不断的从0x0A寄存器的STC位读取是否调谐完成。
        # 当读到调谐完成，需要将0x03的TUNE位设置为0，结束调谐。
        while True:
            this.ReadRegisters()
            if( (this.registers[this.REG_STATUSRSSI] & (1<<this.SI4703_STC)) != 0): break #tuning complete
        this.ReadRegisters()
        this.registers[this.REG_CHANNEL] &= ~(1<<this.SI4703_TUNE) #Clear the tune after a tune has completed
        this.WriteRegisters()
        
    def GetChannel(this):
        # 读取0x03寄存器的[9:0]位计算频率。主要用于seek操作以后的频率获取。
        this.ReadRegisters()
        return ((this.registers[this.REG_READCHAN] & this.SI4703_READCHAN_MASK) + 875) # Mask out everything but the lower 10 bits

    def SetVolume(this,volume):
        # 设置音量，0x05的[3:0]为音量位。
        this.ReadRegisters()
        if(volume < 0): volume = 0
        if(volume > 15): volume = 15
        this.registers[this.REG_SYSCONFIG2] &= 0xFFF0 # 清除音量位
        this.registers[this.REG_SYSCONFIG2] |= volume # 设置新音量值
        this.WriteRegisters()
        
    def GetVolume(this):
        # 读取当前音量
        this.ReadRegisters()
        return (this.registers[this.REG_SYSCONFIG2] & this.SI4703_VOLUME_MASK)
        
    def SeekUp(this):
        # 向seek方法传入1，使向频率更大的方向搜索
        this.Seek(this.SI4703_SEEK_UP)
        
    def SeekDown(this):
        # 向seek方法传入0，使向频率更小的方向搜索
        this.Seek(this.SI4703_SEEK_DOWN)
    
    def Seek(this,seekDirection):
        this.ReadRegisters()
        # 设置搜索模式，是否在到达频段最大或最小频率时，是否从另一端继续搜索
        this.registers[this.REG_POWERCFG] |= (1<<this.SI4703_SKMODE)
        # 根据传参设置搜索方向
        if(seekDirection == this.SI4703_SEEK_DOWN):
            this.registers[this.REG_POWERCFG] &= ~(1<<this.SI4703_SEEKUP)
        else:
            this.registers[this.REG_POWERCFG] |= 1<<this.SI4703_SEEKUP
        # 设置开始搜索位
        this.registers[this.REG_POWERCFG] |= (1<<this.SI4703_SEEK)
        this.WriteRegisters() #Seeking will now start
        
        #同调谐一样，需要等待STC位判断搜索是否完成。
        while True:
            this.ReadRegisters()
            if( (this.registers[this.REG_STATUSRSSI] & (1<<this.SI4703_STC)) != 0):
                break
        this.ReadRegisters()
        this.registers[this.REG_POWERCFG] &= ~(1<<this.SI4703_SEEK) # 在搜索完成以后，清除搜索位。
        this.WriteRegisters()
