# Original is 480:360
# With moons, horizontal resolution scales 4x, so 1920:360
# Scaled down horizontal must be divisible by 4 to map to moons
# Some options are
# - 64:12, really 16:12 [OK]
# - 80:15, really 20:15
# - 128:24, really 32:24
# - 192:36, really 48:36 [OK]

# SCALE="192:36"
# OUTNAME="frames_48_36"
SCALE="64:12"
OUTNAME="frames_16_12"

mkdir "$OUTNAME"

# https://video.stackexchange.com/a/28759
ffmpeg -i bad_apple.mp4 \
  -f lavfi -i color=Gray:s=480x360 \
  -f lavfi -i color=Black:s=480x360 \
  -f lavfi -i color=White:s=480x360 \
  -filter_complex "threshold,scale=$SCALE,format=monob" \
  "$OUTNAME/%04d.bmp"

pushd "$OUTNAME"
tar --create --file "../$OUTNAME.tar" *
popd

rm -r "$OUTNAME"
