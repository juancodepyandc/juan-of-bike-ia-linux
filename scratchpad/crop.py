from PIL import Image
import os
def crop(src,box,out):
    Image.open(src).crop(box).save(out)
# a35: face ~ (380,170,540,320); forearm ~ (600,320,780,420)
for lab in ["homme4","nospec","spec070"]:
    p=f"scratchpad/viewout/{lab}_a35.png"
    if os.path.exists(p):
        crop(p,(360,160,560,340),f"scratchpad/crop_{lab}_face.png")
# stack faces horizontally
imgs=[Image.open(f"scratchpad/crop_{l}_face.png") for l in ["homme4","nospec","spec070"]]
w=sum(i.width for i in imgs); h=max(i.height for i in imgs)
canvas=Image.new("RGB",(w,h),(20,20,20))
x=0
for i in imgs: canvas.paste(i,(x,0)); x+=i.width
canvas.save("scratchpad/faces_compare.png")
print("saved", canvas.size)
