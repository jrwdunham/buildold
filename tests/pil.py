import Image

im = Image.open('media/sample.jpg')
im.thumbnail((200, 200), Image.ANTIALIAS)
im.save('media/small_sample.jpg')

im = Image.open('media/sample.png')
im.thumbnail((200, 200), Image.ANTIALIAS)
im.save('media/small_sample.png')

im = Image.open('media/sample.gif')
im.thumbnail((200, 200), Image.ANTIALIAS)
im.save('media/small_sample.gif')

