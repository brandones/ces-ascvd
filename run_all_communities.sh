#! /usr/bin/env bash

communities=( Capitan Honduras Laguna Letrero Matazano Monterrey Plan_Alta Plan_Baja Reforma Salvador Soledad )

output_data_files=()
no_data=()

for c in "${communities[@]}"
do
    ./extract_chol_records.py $c
    input_filename="Output/$c/ascvd-input.csv"
    if [ -f $input_filename ]; then
        ./run_ascvd.py $c
    fi
    output_filename="Output/$c/ascvd-output.csv"
    if [ -f $output_filename ]; then
        output_data_files+=( $output_filename )
    else
        no_data+=( $c )
    fi
done

cat ${output_data_files[@]} >Output/ascvd-all.csv

echo
echo
echo "No data for ${no_data[@]}"

