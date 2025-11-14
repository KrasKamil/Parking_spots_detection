### Parking Detection Parameters

## Dry / Wet Environment


```bash
python ./app.py -l blok_wet --mode video --blur_kernel 3 3 --blur_sigma 2 --threshold_block 25 --threshold_c 19 --median_blur_kernel 5 --dilate_kernel 3 3 --dilate_iterations 1 --output results/blok_wet_balanced.mp4
```
## BLOK
```
python ./app.py -l blok --mode video --blur_kernel 5 5 --blur_sigma 2 --threshold_block 25 --threshold_c 13 --median_blur_kernel 5 --dilate_kernel 5 5 --dilate_iterations 1
```

## Dry / Wet Environment (BLOK 2 )
```bash
python ./app.py -l blok_2 --mode video --blur_kernel 5 5 --blur_sigma 2 --threshold_block 25 --threshold_c 19 --median_blur_kernel 5 --dilate_kernel 5 5 --dilate_iterations 1
```

## Wet spots ( Blok 4 )
```bash
python ./app.py -l blok_4 --mode video --blur_kernel 3 3 --blur_sigma 2 --threshold_block 25 --threshold_c 19 --median_blur_kernel 5 --dilate_kernel 3 3 --dilate_iterations 1
```