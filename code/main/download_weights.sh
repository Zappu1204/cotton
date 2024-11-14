script_dir=$(realpath $(dirname "$0"))
echo "$script_dir"
FILE=result/Top_1024x768_COTTON/weights
if ! test -d "$FILE"; then
    echo "$FILE not exists."
    curl "https://drive.usercontent.google.com/download?id=19_tXE7VSoT_z2JRZXAKuObM8T_w39WLS&export=download&confirm=t" -o $script_dir/result/Top_1024x768_COTTON/weights.zip
    unzip $script_dir/result/Top_1024x768_COTTON/weights.zip -d $script_dir/result/Top_1024x768_COTTON/
    rm $script_dir/result/Top_1024x768_COTTON/weights.zip
fi

FILE=result/Top_1024x768_DressCode/weights
if ! test -d "$FILE"; then
    echo "$FILE not exists."
    curl "https://drive.usercontent.google.com/download?id=1HPg4Qv3vorp7D9Cd4rn2inKx8J-nQJI4&export=download&confirm=t" -o $script_dir/result/Top_1024x768_DressCode/weights.zip
    unzip $script_dir/result/Top_1024x768_DressCode/weights.zip -d $script_dir/result/Top_1024x768_DressCode/
    rm $script_dir/result/Top_1024x768_DressCode/weights.zip
fi