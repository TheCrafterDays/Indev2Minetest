import argparse
import math
import nbtlib
import numpy
import os
import requests
import shutil
import sqlite3
import zlib
from io import BytesIO
from nbtlib import parse_nbt, Path
from nbtlib.tag import String, List, Compound, IntArray, ByteArray
from numpy import int64
from os.path import exists

def rgb_to_hex(rgb):
    return '%02x%02x%02x' % rgb

parser = argparse.ArgumentParser()
parser.add_argument("IndevWorld")

args = parser.parse_args()

IndevWorld = args.IndevWorld

IndevFile = nbtlib.load(IndevWorld)

Indev_mclevel = IndevFile['MinecraftLevel'] 
Indev_Env = Indev_mclevel['Environment'] 
Indev_Map = Indev_mclevel['Map'] 
Indev_About = Indev_mclevel['About'] 

Indev_WorldSizeX = int(Indev_Map['Width'])
Indev_WorldSizeY = int(Indev_Map['Height'])
Indev_WorldSizeZ = int(Indev_Map['Length'])
Indev_Blocks = numpy.array(Indev_Map['Blocks'])
Indev_WorldName = Indev_About['Name']

Indev_Blocks_3D = Indev_Blocks.reshape((Indev_WorldSizeY,Indev_WorldSizeZ,Indev_WorldSizeX))

MinetestBlocks = [["air","Air"],
["default:stone","Stone"],
["default:dirt_with_grass","Grass Block"],
["default:dirt","Dirt"],
["default:cobble","Cobblestone"],
["default:wood","Planks"],
["default:sapling","Sapling"],
["default:tinblock","Bedrock"],
["default:water_source","Flowing Water"],
["default:water_source","Stationary Water"],
["default:lava_source","Flowing Lava"],
["default:lava_source","Stationary Lava"],
["default:sand","Sand"],
["default:gravel","Gravel"],
["default:stone_with_gold","Gold Ore"],
["default:stone_with_iron","Iron Ore"],
["default:stone_with_coal","Coal Ore"],
["default:tree","Wood"],
["default:leaves","Leaves"],
["wool:yellow","Sponge"],
["default:glass","Glass"],
["wool:red","Red Cloth"],
["wool:orange","Orange Cloth"],
["wool:yellow","Yellow Cloth"],
["wool:green","Chartreuse Cloth"],
["wool:green","Green Cloth"],
["wool:green","Spring Green Cloth"],
["wool:cyan","Cyan Cloth"],
["wool:blue","Capri Cloth"],
["wool:violet","Ultramarine Cloth"],
["wool:violet","Violet Cloth"],
["wool:violet","Purple Cloth"],
["wool:magenta","Magenta Cloth"],
["wool:magenta","Rose Cloth"],
["wool:black","Dark Gray Cloth"],
["wool:grey","Light Gray Cloth"],
["wool:white","White Cloth"],
["flowers:dandelion_yellow","Dandelion"],
["flowers:rose","Rose"],
["flowers:mushroom_brown","Brown Mushroom"],
["flowers:mushroom_red","Red Mushroom"],
["default:goldblock","Block of Gold"],
["default:copperblock","Block of Iron"],
["stairs:slab_steelblock","Double Slab"],
["stairs:slab_steelblock","Slab"],
["default:brick","Bricks"],
["tnt:tnt","TNT"],
["default:bookshelf","Bookshelf"],
["default:mossycobble","Mossy Cobblestone"],
["default:obsidian","Obsidian"],
["default:torch","Torch"],
["fire:permanent_flame","Fire"],
["default:water_source","Water Spawner"],
["default:lava_source","Lava Spawner"],
["default:chest","Chest"],
["air","Gear"],
["default:stone_with_diamond","Diamond Ore"],
["default:diamondblock","Block of Diamond"],
["default:pine_wood","Crafting Table"],
["default:grass_2","Crops"],
["default:dirt_with_coniferous_litter","Farmland"],
["default:furnace","Furnace"],
["default:furnace","Lit Furnace"]]

# ---------------------------- Indev Map to Minetest World ----------------------------

print('Indev2Minetest: World Conversion')

def writeU8(os, u8):
    os.write(bytes((u8&0xff,)))

def writeU16(os, u16):
    os.write(bytes(((u16>>8)&0xff,)))
    os.write(bytes((u16&0xff,)))

def writeU32(os, u32):
    os.write(bytes(((u32>>24)&0xff,)))
    os.write(bytes(((u32>>16)&0xff,)))
    os.write(bytes(((u32>>8)&0xff,)))
    os.write(bytes((u32&0xff,)))

def writeString(os, s):
    b = bytes(s, "utf-8")
    writeU16(os, len(b))
    os.write(b)

def writeLongString(os, s):
    b = bytes(s, "utf-8")
    writeU32(os, len(b))
    os.write(b)

def bytesToInt(b):
    s = 0
    for x in b:
        s = (s<<8)+x
    return s

def getBlockAsInteger(Xval, Yval, Zval):
    return int64(Zval*16777216 + Yval*4096 + Xval)

def getblock(blockposX, blockposZ, blockposY):
  global Indev_Block
  Indev_Block = 0
  if blockposX < Indev_WorldSizeX:
    if blockposY < Indev_WorldSizeY:
      if blockposZ < Indev_WorldSizeZ:
        Indev_Block = Indev_Blocks_3D[blockposY][blockposZ][blockposX]

print(str(Indev_WorldSizeX) + ' ' + str(Indev_WorldSizeY) + ' ' + str(Indev_WorldSizeZ))

def round_down(n, decimals=0):
    multiplier = 10 ** decimals
    return math.floor(n * multiplier) / multiplier

if not os.path.isdir('./output/'):
    os.makedirs('./output/')


MT_WorldSizeX = int(round_down(Indev_WorldSizeX / 16))
MT_WorldSizeY = int(round_down(Indev_WorldSizeY / 16))
MT_WorldSizeZ = int(round_down(Indev_WorldSizeZ / 16))

MT_CurrentChunkX = 0
MT_CurrentChunkY = 0
MT_CurrentChunkZ = 0
MT_RealCurrentChunkX = 0

ConversionComplete = 0

Indev_WorldSpawn = Indev_Map['Spawn']
Indev_SpawnX = int(Indev_WorldSpawn[0])
Indev_SpawnY = int(Indev_WorldSpawn[1])
Indev_SpawnZ = int(Indev_WorldSpawn[2])

MT_SpawnX = Indev_SpawnX * -1 + Indev_WorldSizeX

playersfile = sqlite3.connect("./output/players.sqlite")
playersfile_cur = playersfile.cursor()

playersfile_cur.execute("CREATE TABLE `player` (`name` VARCHAR(50) NOT NULL,`pitch` NUMERIC(11, 4) NOT NULL,`yaw` NUMERIC(11, 4) NOT NULL,`posX` NUMERIC(11, 4) NOT NULL,`posY` NUMERIC(11, 4) NOT NULL,`posZ` NUMERIC(11, 4) NOT NULL,`hp` INT NOT NULL,`breath` INT NOT NULL,`creation_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,`modification_date` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY (`name`))")
playersfile_cur.execute("CREATE TABLE `player_inventories` (   `player` VARCHAR(50) NOT NULL, `inv_id` INT NOT NULL,  `inv_width` INT NOT NULL, `inv_name` TEXT NOT NULL DEFAULT '',  `inv_size` INT NOT NULL,  PRIMARY KEY(player, inv_id),   FOREIGN KEY (`player`) REFERENCES player (`name`) ON DELETE CASCADE )")

playersfile_cur.execute('INSERT INTO player_inventories VALUES ("singleplayer", 0, 0, "main", 32)')
playersfile_cur.execute('INSERT INTO player_inventories VALUES ("singleplayer", 1, 0, "craft", 9)')
playersfile_cur.execute('INSERT INTO player_inventories VALUES ("singleplayer", 2, 0, "craftpreview", 1)')
playersfile_cur.execute('INSERT INTO player_inventories VALUES ("singleplayer", 3, 0, "craftresult", 1)')

playersfile_cur.execute("CREATE TABLE `player_inventory_items` (   `player` VARCHAR(50) NOT NULL, `inv_id` INT NOT NULL,  `slot_id` INT NOT NULL, `item` TEXT NOT NULL DEFAULT '',  PRIMARY KEY(player, inv_id, slot_id),   FOREIGN KEY (`player`) REFERENCES player (`name`) ON DELETE CASCADE )")

for x in range(0, 32):
    playersfile_cur.execute('INSERT INTO player_inventory_items VALUES ("singleplayer", 0, ' + str(x) + ', " ")')

for x in range(0, 9):
    playersfile_cur.execute('INSERT INTO player_inventory_items VALUES ("singleplayer", 1, ' + str(x) + ', " ")')

playersfile_cur.execute('INSERT INTO player_inventory_items VALUES ("singleplayer", 2, 0, "")')
playersfile_cur.execute('INSERT INTO player_inventory_items VALUES ("singleplayer", 3, 0, "")')

playersfile_cur.execute("CREATE TABLE `player_metadata` (    `player` VARCHAR(50) NOT NULL,    `metadata` VARCHAR(256) NOT NULL,    `value` TEXT,    PRIMARY KEY(`player`, `metadata`),    FOREIGN KEY (`player`) REFERENCES player (`name`) ON DELETE CASCADE )")

spawncmd = 'INSERT INTO player VALUES ("singleplayer", 60, 0, ' + str(MT_SpawnX * 10) + ', ' + str(Indev_SpawnY * 10) + ', ' + str(Indev_SpawnZ * 10) + ', ' + '16, 10, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)'

playersfile_cur.execute(spawncmd)

playersfile.commit()
playersfile.close()

mapsqlfile = sqlite3.connect("./output/map.sqlite")
mapsqlfilecur = mapsqlfile.cursor()

mapsqlfilecur.execute("CREATE TABLE IF NOT EXISTS `blocks` (\
`pos` INT NOT NULL PRIMARY KEY, `data` BLOB);")

while ConversionComplete == 0:
  print(str(MT_CurrentChunkX) + ' ' + str(MT_CurrentChunkY) + ' ' + str(MT_CurrentChunkZ))

  mapblockdata = BytesIO()  
  writeU8(mapblockdata, 24)  
    
  flags = 0x00  
  flags |= 0x02  
  writeU8(mapblockdata, flags)  
  writeU8(mapblockdata, 2) # content_width  
  writeU8(mapblockdata, 2) # params_width  
    
  # Bulk node data  
  zlibnodedata = BytesIO()  
    
  Indev_X_BlockPosition = 0  
  Indev_Y_BlockPosition = 0  
  Indev_Z_BlockPosition = 0  
    
  MT_BlocksList = []  
    
  while Indev_Z_BlockPosition <= 15:  

      Indev_X_RealBlockPosition = Indev_X_BlockPosition*-1 + 15
      IndevMT_X_BlockPosition = Indev_X_RealBlockPosition + MT_CurrentChunkX * 16  
      IndevMT_Y_BlockPosition = Indev_Y_BlockPosition + MT_CurrentChunkY * 16  
      IndevMT_Z_BlockPosition = Indev_Z_BlockPosition + MT_CurrentChunkZ * 16  
      getblock(IndevMT_X_BlockPosition, IndevMT_Z_BlockPosition, IndevMT_Y_BlockPosition)  
      # print(str(IndevMT_X_BlockPosition) + ' ' + str(IndevMT_Y_BlockPosition) + ' ' + str(IndevMT_Z_BlockPosition) + ' ' + str(Indev_Block))  
      MT_BlocksList.append(Indev_Block)  
      if 15 == Indev_X_BlockPosition:  
        Indev_X_BlockPosition = 0  
        if 15 == Indev_Y_BlockPosition:  
          Indev_Y_BlockPosition = 0  
          if 16 != Indev_Z_BlockPosition:  
            Indev_Z_BlockPosition = Indev_Z_BlockPosition + 1  
        else:  
          Indev_Y_BlockPosition = Indev_Y_BlockPosition + 1  
      else:  
        Indev_X_BlockPosition = Indev_X_BlockPosition + 1  
      writeU16(zlibnodedata, Indev_Block)

  ByteRepeat = 1  
  while ByteRepeat <= 4096:  
      ByteRepeat += 1  
      writeU8(zlibnodedata, 15)  
    
  ByteRepeat = 1  
  while ByteRepeat <= 4096:  
      ByteRepeat += 1  
      writeU8(zlibnodedata, 0)  
    
  mapblockdata.write(zlib.compress(zlibnodedata.getvalue()))  

  zlibmetadata = BytesIO()  
  writeU8(zlibmetadata, 1)  
  mapblockdata.write(zlib.compress(zlibmetadata.getvalue()))  
       
  writeU8(mapblockdata, 0) #nodetimer_version
  
  # Static objects  
  writeU8(mapblockdata, 0) # Version  
  writeU16(mapblockdata, 0) # Number of objects  
    
  # Timestamp  
  writeU32(mapblockdata, 0x0000027a) # BLOCK_TIMESTAMP_UNDEFINED  
    
  MT_UsedBlocksList = []  
    
  for word in MT_BlocksList:  
      if word not in MT_UsedBlocksList:  
          MT_UsedBlocksList.append(word)  
    
  # Name-ID mapping  
  writeU8(mapblockdata, 0) # Version  
  writeU16(mapblockdata, len(MT_UsedBlocksList))  
    
  for i in range(len(MT_UsedBlocksList)):  
      BlockName = MinetestBlocks[MT_UsedBlocksList[i]][0]
      if BlockName == "":  
          BlockName = 'air'  
      writeU16(mapblockdata, MT_UsedBlocksList[i])  
      #print(BlockName)  
      writeString(mapblockdata, BlockName)


  MT_RealCurrentChunkX = MT_CurrentChunkX*-1 + MT_WorldSizeX
  MT_Pos = getBlockAsInteger(MT_RealCurrentChunkX, MT_CurrentChunkY, MT_CurrentChunkZ)
  mapsqlfilecur.execute("INSERT INTO blocks VALUES (?,?)", (int(MT_Pos), mapblockdata.getvalue()))
  if MT_WorldSizeX <= MT_CurrentChunkX:
    MT_CurrentChunkX = 0
    if MT_WorldSizeY <= MT_CurrentChunkY:
      MT_CurrentChunkY = 0
      if MT_WorldSizeZ <= MT_CurrentChunkZ:
        ConversionComplete = 1
      else:
        MT_CurrentChunkZ = MT_CurrentChunkZ + 1
    else:
      MT_CurrentChunkY = MT_CurrentChunkY + 1
  else:
    MT_CurrentChunkX = MT_CurrentChunkX + 1
  
mapsqlfile.commit()
mapsqlfile.close()

worldmtfile = open("output/world.mt", "w")
worldmtfile.write('enable_damage = true\n')
worldmtfile.write('creative_mode = true\n')
worldmtfile.write('auth_backend = sqlite3\n')
worldmtfile.write('player_backend = sqlite3\n')
worldmtfile.write('backend = sqlite3\n')
worldmtfile.write('gameid = minetest\n')
worldmtfile.write('world_name = ' + Indev_WorldName + '\n')
worldmtfile.write('server_announce = false\n')
worldmtfile.close()

mapmetafile = open("output/map_meta.txt", "w")
mapmetafile.write('mg_flags = caves, dungeons, light, decorations, biomes, ores\n')
mapmetafile.write('chunksize = 5\n')
mapmetafile.write('mapgen_limit = 31000\n')
mapmetafile.write('water_level = 1\n')
mapmetafile.write('seed = 0\n')
mapmetafile.write('mg_name = singlenode\n')
mapmetafile.write('[end_of_params]\n')
mapmetafile.close()
