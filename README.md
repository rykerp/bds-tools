# bds-tools
Import DSON files into Blender

## Installation
See https://www.blender.org/manual/advanced/scripting/python/add_ons.html#installation-of-a-3rd-party-add-on

## Configuration
Set your content root directory in the add-on preferences (File -> User Preferences -> Add-ons -> BDS-Tools)

### Import asset
* To import an environment or new figure make sure that **no** armature object is selected
* To import a clothing or hair item and parent to an already existing figure select the armature object of the figure first
* Use File -> Import -> DSON/duf asset (.duf)
* Locate .duf file with asset
* Hit import button

### Apply morph
* Morphs are automatically imported when importing an asset
* Select mesh object with morphs (not the armature object)
* Check morph panel in BDS-Tools tab in the tool bar (on the left side of 3D view)

### Import pose
* Select armature object (named rig-*) to which the pose should be applied
* Use File -> Import -> DSON/duf pose (.duf)
* Locate .duf file with pose
* Hit import button
