# -*- coding: utf-8 -*-
'''

Use Ghostscript (gs) to convert pdf to png. Solution found in /tests/conftest.py

render_png() shape size A4 210x297mm

Parsing PDF in imagemagick has been disabled 
 - it can be enabled manually by editing /etc/ImageMagick-7/policy.xml file and removing PDF 
 from <policy domain="coder" rights="none" pattern="{PS,PS2,PS3,EPS,PDF,XPS}" />
 
TODO: change convert to other converting. Don't disable ImageMagick's security checks to make this work.


'''
import os
from os import path as osp

import json
from shutil import copyfile

from pdf2image import convert_from_path
from PIL import ImageChops

ABSPATH = osp.dirname( osp.abspath( __file__) )
BASEPATH = osp.join( ABSPATH , "..")
FILESPATH = osp.join( BASEPATH, 'data', 'unittest') 

import unittest


class testCaseBase(unittest.TestCase):
            
    def check_pdf_data( self, data, contents=-1, pages=-1, intern_check:bool=False ):
        ''' Prüft pdf data mit vorher gespeicherten data

        Erzeugt in unittest dir auf dem Server ein dir 'check', um dort die Vergleichsdaten zu speichern

        Parameters
        ----------
        data : dict
            - content: dict
                page_names : dict
            - overlays: dict
            - pages: int
            - pdf_filename: string
            - pdf_filepath: string
        contents : int
            Anzahl der Seiten im Content
        pages : int
            Anzahl der Seiten im PDF
        intern_check:
            Wenn True wird in tests und nicht im normalem pdf Ablegeort geprüft. Default is False

        Returns
        -------
        test_result: dict.

        '''
       
        test_result =  {
            "pdf.filename" : None,
            "pdf.pageCount" : None,
            "pdf.pageNames" : None,
            "pdf.content" : None,
            "pdf.content.pages" : {},
            "pdf.pngPageCount": None,
            "pdf.pngDiff" : None,
            "pdf.pngDiff.pages": {}
        }

        if "pdf_filepath" in data:
            test_result["pdf.filename"] = True
   
        check = {}
        
        #
        # Vorbereitungen
        #

        if intern_check == True:
            test_dir = osp.join( FILESPATH, "pdf" )
            check_dir = osp.join( FILESPATH, "check" )
        else:
            test_dir = os.path.dirname( data["pdf_filepath"] )
            check_dir = osp.join( test_dir, "check" )
        
        # create the folders if not already exists
        if not osp.exists( check_dir ):
            try:
                os.makedirs( check_dir )
            except IOError as e:
                print("Unable to create dir.", e)

        test_writable = True
        if not os.access(test_dir, os.W_OK):
            test_writable = False
            msg = 'testbase.check_pdf_data: keine Schreibrechte auf: {}'.format( test_dir )
            print(  msg )
            
        check_writable = True
        if not os.access(check_dir, os.W_OK):
            check_writable = False
            msg = 'testbase.check_pdf_data: keine Schreibrechte auf: {}'.format( check_dir )
            print(  msg )
            
        # Dateiname für den Inhalt festlegen
        json_test_name = osp.join( test_dir, data["pdf_filename"] ) + ".json"
        json_check_name = osp.join( check_dir, data["pdf_filename"] ) + ".json"

        pdf_check_name = osp.join( check_dir, data["pdf_filename"] )

        new_name = osp.splitext(data["pdf_filepath"])[0]

        # changeback resources path in content
        if "_variables" in data:
            json_data = json.dumps( data["content"])
           
            json_data = json_data.replace( data["_variables"]["resources"], "{{resources}}")
            json_data = json_data.replace( data["_variables"]["templates"], "{{templates}}")
            data["content"] = json.loads(json_data)
        
        # immer den content in unittest ablegen
        if test_writable:
            with open(json_test_name, "w" ) as json_file:
                json.dump( data["content"] , json_file, indent=2 )
        
        if check_writable:
            # beim erstenmal content nach check kopieren
            if not os.path.exists( json_check_name ):
                try:
                    copyfile(json_test_name, json_check_name)
                except IOError as e:
                    print("Unable to copy file.", e)

            # beim erstenmal pdf nach check kopieren
            if not os.path.exists( pdf_check_name ):
                try:
                    copyfile(data["pdf_filepath"], pdf_check_name)
                except IOError as e:
                    print("Unable to copy file.", e)

        #
        # Überprüfungen
        #

        # passende check daten (json_check_name) laden
        with open( json_check_name ) as json_file:
            check = json.load( json_file )
    
        page_names = data["content"].keys()
        # Anzahl der Bereiche prüfen
        test_result["pdf.pageCount"] = False
        if len(page_names) > -1:
            test_result["pdf.pageCount"] = True
                   
        # Namen der Bereiche
        test_result["pdf.pageNames"] = False
        if page_names == check.keys():
            test_result["pdf.pageNames"] = True

        # einige content Inhalte prüfen
        from bs4 import BeautifulSoup
        test_result["pdf.content"] = False
        test_result["pdf.content.pages"] = {}
        for page_name, content in data["content"].items():
            bs_data = BeautifulSoup( content, 'html.parser')
            bs_check = BeautifulSoup( check[ page_name ], 'html.parser')

            # die text Bereiche
            data_text_list = bs_data.find_all('div', {"class": "text"} )
            check_text_list = bs_check.find_all('div', {"class": "text"} )
            if len(data_text_list) == len(check_text_list):
                for i in range(min(len(data_text_list), len(check_text_list))):
                    test_result["pdf.content.pages"][i+1] = False
                    if data_text_list[i] == check_text_list[i]:
                        test_result["pdf.content.pages"][i+1] = True

        r = {v: k for k, v in test_result["pdf.content.pages"].items()}
        if not False in r:
            test_result["pdf.content"] = True

        # vergleich mit pdf2image
        # , pdf_check_name
        dpi = 300
        images = convert_from_path( data["pdf_filepath"], dpi=dpi )
        check_images = convert_from_path( pdf_check_name, dpi=dpi )
        test_result["pdf.pngPageCount"] = False  
        if len(images) == len(check_images):
            test_result["pdf.pngPageCount"] = True
        
        # jetzt die einzelnen Seiten prüfen, bei Fehlern wird das diff gespeichert
        diff_max = 500.0
        test_result["pdf.pngDiff"] = False
        test_result["pdf.pngDiff.pages"] = {}
        diffErrors = 0
        i = 0
        for img, check_img in zip(images, check_images):
            i += 1
            diff = ImageChops.difference(img, check_img)
            diff_qual = len(set(diff.getdata()))
            typ = "diff"

            if diff_qual > diff_max:
                typ = "error"
                diffErrors += 1
                test_result["pdf.pngDiff.pages"][i+1] = False
            else:
                test_result["pdf.pngDiff.pages"][i+1] = True

            if typ == "error":
                name = "{}.{:02.0f}.{}.png".format( new_name, i+1, typ)
                diff.save( name )

        if diffErrors == 0:
            test_result["pdf.pngDiff"] = True
        
        return test_result
       
