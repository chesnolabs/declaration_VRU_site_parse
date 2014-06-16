declaration_VRU_site_parse
==========================

The python 2.7 script written to get information about the number of deputies declarations on Rada website and the data in this declaration.

Windows: Launch the script from command line by just typing filename and pressing enter. The script will create c:\dec7 folder where all the files will be saved.

The results of script looks as following:
1. list.csv - the list of declaration available on Verkhovna Rada website. Consists of 3 column: deputy fullname, declaration year and the way declaration publishe (pdf/data)
2. no_dec.csv - the list of declaration the script could not get access to.
3. no_page.csv - the list of deputies whose page wasn't available for the script. So script do not know whether these deputies' declarations were published.
4. declarations.tsv - the parsed declaration data. All the declaration in "data" format are saved in this file.
5. dozens of .pdf files - the scanned copies of MPs' declaration published in .pdf format.

If the script fails to get access to lot of MPs, try increasing SlEEP_TIME parameter. Default value is 5.
