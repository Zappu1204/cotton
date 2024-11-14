script_dir=$(realpath $(dirname "$0"))
echo "$script_dir"
FILE=CIHP_PARSING/checkpoint
if ! test -d "$FILE"; then
    echo "$FILE not exists."
    curl "https://drive.usercontent.google.com/download?id=1QFUujOeUY9YRz5_Mq-TBYNfP4ft-yhMJ&export=download&confirm=t" -o $script_dir/CIHP_PARSING/checkpoint.zip && \
    unzip $script_dir/CIHP_PARSING/checkpoint.zip -d $script_dir/CIHP_PARSING
    rm $script_dir/CIHP_PARSING/checkpoint.zip
fi

FILE=U2Net/saved_models
if ! test -d "$FILE"; then
    echo "$FILE not exists."
    curl "https://drive.usercontent.google.com/download?id=1Mxf0T_IIZfN6DG5k7Ibrh2GvwZ11N7u5&export=download&confirm=t" -o $script_dir/U2Net/saved_models.zip
    unzip $script_dir/U2Net/saved_models.zip -d $script_dir/U2Net
    rm $script_dir/U2Net/saved_models.zip
fi

FILE=Sleeve_Classifier/weights
if ! test -d "$FILE"; then
    echo "$FILE not exists."
    curl "https://drive.usercontent.google.com/download?id=1BYMPYjhzURv6p_Ow0LWWJUnpgZnNHCby&export=download&confirm=t" -o $script_dir/Sleeve_Classifier/weights.zip
    unzip $script_dir/Sleeve_Classifier/weights.zip -d $script_dir/Sleeve_Classifier
    rm $script_dir/Sleeve_Classifier/weights.zip
fi

FILE=lower_clf/weights
if ! test -d "$FILE"; then
    echo "$FILE not exists."
    curl "https://drive.usercontent.google.com/download?id=1WjBsVuVH3A3ZkDHiDkP4eGg5s9t8tCjY&export=download&confirm=t" -o $script_dir/lower_clf/weights.zip
    unzip $script_dir/lower_clf/weights.zip -d $script_dir/lower_clf
    rm $script_dir/lower_clf/weights.zip
fi

FILE=Cloth2Skeleton/weights
if ! test -d "$FILE"; then
    echo "$FILE not exists."
    curl "https://drive.usercontent.google.com/download?id=1M5YE9HhG73x4EAcBu9WP-31OR2Awyh6W&export=download&confirm=t" -o $script_dir/Cloth2Skeleton/weights.zip
    unzip $script_dir/Cloth2Skeleton/weights.zip -d $script_dir/Cloth2Skeleton
    rm $script_dir/Cloth2Skeleton/weights.zip
fi

FILE=ClothSegmentation/weights
if ! test -d "$FILE"; then
    echo "$FILE not exists."
    curl "https://drive.usercontent.google.com/download?id=1j11XCO6cD3nYo-4ObQHuYwe7Ocy5BoGw&export=download&confirm=t" -o $script_dir/ClothSegmentation/weights.zip
    unzip $script_dir/ClothSegmentation/weights.zip -d $script_dir/ClothSegmentation
    rm $script_dir/ClothSegmentation/weights.zip
fi

FILE=Self-Correction-Human-Parsing/exp-schp-201908301523-atr.pth
if ! test -f "$FILE"; then
    echo "$FILE not exists."
    curl "https://drive.usercontent.google.com/download?id=1airhKX-o8AIxs3M0uFU4BNvwc5YZo7Xd&export=download&confirm=t" -o $script_dir/Self-Correction-Human-Parsing/exp-schp-201908301523-atr.pth
fi