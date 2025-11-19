### Parking Detection Parameters

## Dry / Wet Environment


```bash
python ./app.py -l blok_wet --mode video --blur_kernel 3 3 --blur_sigma 2 --threshold_block 25 --threshold_c 19 --median_blur_kernel 5 --dilate_kernel 3 3 --dilate_iterations 1 
```
## BLOK           
```bash
python ./app.py -l blok --mode video --blur_kernel 5 5 --blur_sigma 2 --threshold_block 25 --threshold_c 18 --median_blur_kernel 5 --dilate_kernel 5 5 --dilate_iterations 1

```                
## Dry / Wet Environment (BLOK 2 )
```bash
python ./app.py -l blok_2 --mode video --blur_kernel 5 5 --blur_sigma 2 --threshold_block 25 --threshold_c 19 --median_blur_kernel 5 --dilate_kernel 5 5 --dilate_iterations 1
```

## Wet spots ( Blok 4 )
```bash
python ./app.py -l blok_4 --mode video --blur_kernel 3 3 --blur_sigma 2 --threshold_block 25 --threshold_c 19 --median_blur_kernel 5 --dilate_kernel 3 3 --dilate_iterations 1
```
## Japan ( Possibly night when checking due to time zone)
```bash
python ./app.py -l blok --mode video --blur_kernel 5 5 --blur_sigma 2 --threshold_block 25 --threshold_c 17 --median_blur_kernel 5 --dilate_kernel 5 5 --dilate_iterations 1
```
## Rynek_jaslo (live camera)
```bash
 python ./app.py -l rynek_jaslo --threshold_c 13
 ```