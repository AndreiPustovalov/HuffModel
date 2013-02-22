# ---------------------------------------------------------------------------
# HuffModel.py 
# Created: 4/13/2007 by Drew Flater
# Usage: Creating probability-based trade areas for retail stores 
# ---------------------------------------------------------------------------

# Import system modules
import sys, string, arcgisscripting, os, traceback, shutil, re

# Create the Geoprocessor object
gp = arcgisscripting.create(9.3)

# Set overwrite 
gp.overwriteoutput = 1

def AddPrintMessage(msg, severity):
    print msg
    if severity == 0: gp.AddMessage(msg)
    elif severity == 1: gp.AddWarning(msg)
    elif severity == 2: gp.AddError(msg)

# Start traceback Try-Except statement:
try:
    # Script parameters...
    stores = gp.getparameterastext(0)
    store_name = gp.getparameterastext(1)
    store_attr = gp.getparameterastext(2)
    outfolder = gp.getparameterastext(3)
    fc_name = gp.getparameterastext(4)
    studyarea = gp.getparameterastext(5)
    blockgroups = gp.getparameterastext(6)
    sales = gp.getparameterastext(7)
    distances = gp.getparameterastext(8)
    streets = gp.getparameterastext(9)
    x = gp.getparameterastext(10)
    marketareas = gp.getparameterastext(11)
    potential_st = gp.getparameterastext(12)
    surfaces = gp.getparameterastext(13)

    # Make sure ArcInfo license is available
    if gp.productinfo().lower() not in ['arcinfo', 'arcserver']:
        gp.adderror("An ArcInfo or ArcServer license is required to run this tool.")
        sys.exit()
        
    # Establish 'step' progressor settings
    gp.SetProgressor("step", "Checking inputs against parameter requirements..." , 0, 9, 1) 

    # Process: Make output file gdb
    gp.createfilegdb(outfolder, "output.gdb")
    outputgdb = outfolder + "\\output.gdb" + os.sep
    gp.SetProgressorPosition()

    #setparameter as text in lines 623-624
    outfc = outputgdb + fc_name
    outmarkets = outputgdb + "Surface_Markets"
    outpotential = outputgdb + "potential_stores"

    # Check to make sure user has the necessary extensions...
    if distances.lower() == 'true':
        try:
            gp.CheckOutExtension("Network")
        except:
            gp.adderror("Network Analyst extension is not licensed. Uncheck the 'Use Street-Network Travel Times' option to use Straight-Line Distances.")
            sys.exit()
        if streets == "":
            gp.adderror("ERROR 000735: Input analysis network: Value is required.")
            gp.adderror("If the 'Use Street-Network Travel Times' option is checked (TRUE), a valid Street Network Dataset must be provided.")
            sys.exit()
        else:
            desc = gp.describe(streets)
            if desc.datatype not in ["NetworkDataset", "NetworkDatasetLayer"]:
                gp.adderror("If the 'Use Street-Network Travel Times' option is checked (TRUE), a valid Street Network Dataset must be provided.")
                sys.exit()

    if surfaces.lower() == 'true':
        try:
            gp.CheckOutExtension("Spatial")
        except:
            gp.adderror("Spatial Analyst extension is not licensed. Surfaces cannot be interpolated. Uncheck the 'Generate Probability Surfaces' option to process the model without generating surfaces.")
            sys.exit()

    # Check to make sure there are a sufficient number of stores for modeling (>1)
    numstoresondisk = gp.getcount_management(stores).getoutput(0)
    if gp.exists(potential_st):
        numpotentialstores = gp.getcount_management(potential_st).getoutput(0)
    else:
        numpotentialstores = 0        
    if int(numstoresondisk) + int(numpotentialstores) < 2:
        gp.adderror("There are an insufficient number of stores to perform modeling. There must be at least two total records between the Store Locations dataset and the Potential Stores feature set.")
        sys.exit()

    # Check to make sure there are no duplicate field values in the Store Name Field
    desc = gp.describe(stores)
    sNameList = []
    
    cur = gp.SearchCursor(stores)
    row = cur.Next()
    while row :
        sName = row.GetValue(store_name)
        if sName in sNameList:
            gp.adderror("Field values in field '" + str(store_name) + "' are not unique. Use a different field.")
            sys.exit()
        sNameList.append(sName)
        row = cur.Next()
            
    # Check to make sure all input parameters are in a common projected coordinate system
    if blockgroups == "":
        desccs_st = gp.describe(stores)
        sr_st = desccs_st.spatialreference
        desccs_sa = gp.describe(studyarea)
        sr_sa = desccs_sa.spatialreference
        if sr_st.projectionname == sr_sa.projectionname:
            ""
        else:
            gp.adderror("The store and study area feature classes must be in the same projected coordinate system.")
            sys.exit()
    else:
        desccs_st = gp.describe(stores)
        sr_st = desccs_st.spatialreference
        desccs_bg = gp.describe(blockgroups)
        sr_bg = desccs_bg.spatialreference
        desccs_sa = gp.describe(studyarea)
        sr_sa = desccs_sa.spatialreference
        if sr_st.projectionname == sr_bg.projectionname and sr_st.projectionname == sr_sa.projectionname:
            ""
        else:
            gp.adderror("The stores, origin locations, and study area feature classes must be in the same projected coordinate system.")
            sys.exit()

    # Warn that stores with an attribute value of 0 or less will be dropped from analysis
    desc = gp.describe(stores)
    OIDfield = desc.OIDFieldName
    
    cur = gp.SearchCursor(stores)
    row = cur.Next()
    while row :
        attr_val = row.GetValue(store_attr)
        OID_val = row.GetValue(OIDfield)
        if attr_val <= 0:
            gp.addwarning("Feature " + str(OID_val) + " in dataset: " + str(stores) + " has an attractiveness value of less than or equal to zero. This store location will be excluded from modeling.")
        row = cur.Next()

    # Process: Convert Store locations to points and replace nonalphanumeric characters in store names with underscore...
    gp.select(stores, r"in_memory\st", store_attr + " > 0")
    gp.SetProgressorPosition()
    fields = gp.listfields(r"in_memory\st", "*")
    for field in fields:
        if field.required == True:
            ""
        elif field.name == str(store_name):
            ""
        elif field.name == str(store_attr):
            ""
        else:
            gp.deletefield(r"in_memory\st", field.name)
    gp.SetProgressorPosition()
                     
    # If the potential stores feature set contains features, append them to the stores feature class
    if int(numpotentialstores) > 0:
        # If the potential stores feature set has NAME and ATTRACTIVENESS fields, append them to the stores feature class
        fields = gp.listfields(potential_st, "*")
        name_field = 0
        attr_field = 0

        for field in fields:
            if field.name == "NAME":
                name_field = 1
            if field.name == "ATTRACTIVENESS":
                attr_field = 1

        if name_field + attr_field == 2:

            # Make permanent copy of features in Potential Stores feature set
            gp.copyfeatures(potential_st, outputgdb + "potential_stores")

            # Make sure text in potential stores fields fits in the Stores feature class fields
            fields = gp.listfields(r"in_memory\st")
            for field in fields:
                if field.name == store_name:
                    maxlength = field.length
            cur = gp.updatecursor(outputgdb + "potential_stores", "", "", "NAME")
            row = cur.next()
            while row:
                name_orig = row.GetValue("NAME")
                name_new = name_orig.ljust(maxlength)[:maxlength]
                if len(name_orig) > maxlength:
                    set_name = row.setvalue("NAME", name_new)
                else:
                    set_name = row.setvalue("NAME",name_orig)
                cur.Updaterow(row)
                row = cur.next()
            del cur
            del row

            # Create field mappings for appending potential stores to Stores           
            fieldmappings = gp.CreateObject("FieldMappings")
            fieldmappings.AddTable(outputgdb + "potential_stores")
            fieldmappings.AddTable(r"in_memory\st")

            # Map the "NAME" field from the potential stores feature set to the store_name field in st
            fieldmap = fieldmappings.GetFieldMap(fieldmappings.FindFieldMapIndex(store_name))
            fieldmap.AddInputField(outputgdb + "potential_stores", "NAME")

            # Map the "ATTRACTIVENESS" field from the potential stores feature set to the store_attr field in st
            fieldmap = fieldmappings.GetFieldMap(fieldmappings.FindFieldMapIndex(store_attr))
            fieldmap.AddInputField(outputgdb + "potential_stores", "ATTRACTIVENESS")
            fieldmappings.ReplaceFieldMap(fieldmappings.FindFieldMapIndex(store_attr), fieldmap)
            fieldmappings.RemoveFieldMap(fieldmappings.FindFieldMapIndex("ATTRACTIVENESS"))

            gp.append(outputgdb + "potential_stores", r"in_memory\st", "NO_TEST", fieldmappings)
            gp.SetProgressorPosition()

        else:
            gp.addwarning("Your Potential Store Locations features class or layer does not have fields NAME and/or ATTRACTIVENESS. These features have been excluded from the model.")

    # Truncate store names if they are too long (45 characters), or substiture underline for non-supported characters
    fields = gp.listfields(r"in_memory\st")
    for field in fields:
        if field.name == store_name:
            maxlength = field.length
            
    cur = gp.updatecursor(r"in_memory\st", "", "", store_name)
    row = cur.next()
    while row:
        name_orig = row.GetValue(store_name)
        name_num = name_orig.rjust(1)[:1]
        numlist = ['1','2','3','4','5','6','7','8','9','0']
        if name_num in numlist:
            name_orig = "_" + name_orig
        name_new = re.sub('[^a-zA-Z_0-9]', '_', str(name_orig))
        if len(name_new) > maxlength:
            name_new = name_new.ljust(maxlength)[:maxlength]
        name_trunc = name_new.ljust(45)[:45]
        if len(name_new) >=45:
            set_name = row.setvalue(store_name, name_trunc)
        else:
            set_name = row.setvalue(store_name, name_new)
        try:
            cur.Updaterow(row)
        except:
            gp.adderror("Rows in store layer contain bad records.  Problem may have occured if Potential stores were drawn with no NAME added.  Check the geoprocessing 'Results' tab to ensure that the Potential Stores feature set has values in both the NAME and ATTRACTIVENESS fields.")
            sys.exit()
        row = cur.next()
    del cur
    del row
    gp.SetProgressorPosition()

    # If study area contains more than one polygon, dissolve it
    numstudyarea = int(gp.getcount_management(studyarea).getoutput(0))
    if numstudyarea > 1:
        gp.dissolve_management(studyarea, r"in_memory\studyarea")
        cur = gp.searchcursor(r"in_memory\studyarea")
    else:        
        cur = gp.searchcursor(studyarea)
    descunit = gp.describe(studyarea)
    sr = descunit.spatialreference
    row = cur.next()
    area = 0
    # Process: Calculate area of study area
    while row:
        feat = row.shape
        area = feat.Area
        if sr.linearunitname == "Foot_US":
            if area / 5318313.2 > 500: # max number of points
                pointnum = 500
            elif area / 5318313.2 < 100: # min number of points
                pointnum = 100
            else:
                pointnum = area / 5318313.2
                    
        elif sr.linearunitname == "Meter":
            if area / 494089.52 > 500: # max number of points
                pointnum = 500
            elif area / 494089.52 < 100: # min number of points
                pointnum = 100
            else:
                pointnum = area / 494089.52
        else:
            gp.adderror("Your study area feature class does not have a projected coordinate system.  Please project your data or use another data source.")
            sys.exit()
        row = cur.next()

    # Process: Generate random origin points...
    if blockgroups == "":      
        gp.CreateRandomPoints_management("in_memory","bgrandom", studyarea,"", int(pointnum))
        gp.SetProgressorPosition()
 
        gp.merge_management(r"in_memory\st;in_memory\bgrandom",r"in_memory\bg")
        gp.SetProgressorPosition()
        fields = gp.listfields(r"in_memory\bg", "*")
        for field in fields:
            if field.required == True or field.name == "Shape":
                ""
            else:
                gp.deletefield_management(r"in_memory\bg", field.name)
        gp.SetProgressorPosition()

    # Process: Create centroid points from input origin locations
    else:
        gp.FeatureToPoint_management(blockgroups, r"in_memory\bg", "CENTROID")
        gp.SetProgressorPosition()
        # Process: clear attributes in block group points layer by deleting
        fields = gp.listfields(r"in_memory\bg", "*")
        for field in fields:
            if field.required == True:
                ""
            elif field.name == sales:
                ""
            else:
                gp.deletefield_management(r"in_memory\bg", field.name)
                
        gp.SetProgressorPosition()

    # Process: Add ID field for stores and block groups
    gp.AddField_management(r"in_memory\st", "SID", "SHORT", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    gp.AddField_management(r"in_memory\bg", "BID", "SHORT", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
    gp.SetProgressorPosition()
    
    # Process: Calculate ID field for block groups
    desc = gp.describe(r"in_memory\bg")
    gp.CalculateField_management(r"in_memory\bg", "BID", "[" + desc.OIDFieldName + "]")
    gp.SetProgressorPosition()

    # Process: Calculate ID field for stores
    desc = gp.describe(r"in_memory\st")
    gp.CalculateField_management(r"in_memory\st", "SID", "[" + desc.OIDFieldName + "]")
    gp.SetProgressorPosition()

    gp.addmessage("Finished checking inputs against parameter requirements.")
   

######################################################################################################################################################
######################################################################################################################################################
    
    gp.SetProgressor("default", "Saving centroid points from input origin locations......", 0, 1, 2)
    gp.copyfeatures(r"in_memory\bg", outputgdb + "bg_points")
    gp.SetProgressorposition()
    gp.SaveSettings(outfolder + "\\settings.xml")
    gp.SetProgressorposition()
    
    if distances.lower() == 'true':
        gp.SetProgressor("default", "Calculating travel impedance from Origin Locations to Store Destinations......", 0, 1, 1)

        # Figure out Network Dataset attributes for use in Making the OD Cost Matrix
        usetime = ""
        uselength = ""
        cost = ""
        useheirarchy = ""

        desc = gp.describe(streets)
        attributes = desc.attributes
        attributes.reset()
        attribute = attributes.next()
        while attribute:
            if attribute.UsageType == "Cost":
                if attribute.Units in ["Days", "Hours", "Minutes", "Seconds"]:
                    usetime = attribute.Name
                else:
                    uselength = attribute.Name
            if attribute.UsageType == "Heirarchy":
                useheirarchy = "USE_HIERARCHY"
            attribute = attributes.next()

        if usetime != "":
            cost = usetime            
        else:
            cost = uselength
            
        # Process: Make OD Cost Matrix Layer...
        gp.MakeODCostMatrixLayer_na(streets, "OD", cost, "", "", cost, "NO_UTURNS", "OneWay", useheirarchy, "", "STRAIGHT_LINES")

        # Add Origin Locations to OD Matrix
        gp.addlocations_na("OD", "Origins", r"in_memory\bg", "Name BID #;CurbApproach # 0;TargetDestinationCount # #", "1000 Miles", "", "", "MATCH_TO_CLOSEST", "APPEND")
       
        # Add Destination Locations to OD Matrix
        gp.addlocations_na("OD", "Destinations", r"in_memory\st", "Name SID #;CurbApproach # 0;TargetDestinationCount # #", "1000 Miles", "", "", "MATCH_TO_CLOSEST", "APPEND")

        # Process: Solve Origin Destination matrix... 
        gp.Solve_na("OD", "SKIP")
        gp.addmessage("Finished calculating travel impedance ("+cost+") from origin locations to stores.")
        gp.savetolayerfile_management("OD", outfolder + "\\ODafter.lyr")

    # If Network Analyst is not available, calculate distances that are straight line
    else:
        gp.SetProgressor("default", "Calculating straight-line distance from input locations to store destinations...", 0, 1, 1)
        gp.generateneartable(r"in_memory\bg", r"in_memory\st", r"in_memory\tbl", "", "", "", "ALL")
        gp.SetProgressorposition()
        gp.addmessage("Finished calculating straight-line distances from origin locations to stores.")
        
#############################################################################################################################################
#############################################################################################################################################
    
    # Set progressor for stage of process
    numst = gp.getcount_management(r"in_memory\st").getoutput(0)
    count = (7*int(numst)) + 5    

    # If Network Analyst is available, calculate model based on travel time
    if distances.lower() == 'true':
        if surfaces.lower() == 'true':
            gp.SetProgressor("step", "Calculating probabilities and generating surfaces..." , 0, count, 1)
        else:
            gp.SetProgressor("step", "Calculating probabilities..." , 0, count, 1)

        # Process: Make Table from OD lines...
        gp.CopyRows_management("OD\\Lines", outputgdb + "tbl")
        # Process: Delete fields
        gp.deletefield(outputgdb + "tbl", "Name;DestinationRank")
        gp.CopyRows(outputgdb + "tbl", r"in_memory\tbl")
        gp.delete(outputgdb + "tbl")
        gp.SetProgressorPosition() 

        # Process: Delete in-memory OD matrix
        try: 
            gp.delete_management("OD")
        except:
            pass

        # Make minimum travel time 0.1 minutes instead of 0 minutes (for calculation)
        if blockgroups == "":
            cur = gp.updatecursor(r"in_memory\tbl", "Total_" + cost + " = 0")
            row = cur.next()
            while row:
                row.SetValue("Total_" + cost, row.GetValue("Total_" + cost) + .1)
                cur.Updaterow(row)
                row = cur.next()
            del cur
            del row

        # Process: Join store and origin attributes to OD table...
        gp.JoinField(r"in_memory\tbl", "OriginID", r"in_memory\bg", "BID", "BID;" + str(sales))
        gp.SetProgressorPosition() 
        gp.JoinField(r"in_memory\tbl", "DestinationID", r"in_memory\st", "SID", "SID;" + str(store_attr) + ";" + str(store_name))
        gp.delete_management(r"in_memory\st")
        gp.SetProgressorPosition() 

        # Process: Add and Calculate tt_x_att Field ...
        gp.AddField_management(r"in_memory\tbl", "tt_x_att", "FLOAT", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
        if x == "":
            x = 2
        gp.CalculateField_management(r"in_memory\tbl", "tt_x_att","(1/ ([Total_" + cost + "]^" + str(x) + ")) * [" + str(store_attr) + "]")
        gp.SetProgressorPosition()

    # If Network Analyst is not available, calculate model based on straight line distance
    else:
        if surfaces.lower() == 'true':
            gp.SetProgressor("step", "Calculating probabilities and generating surfaces..." , 0, count, 1)
        else:
            gp.SetProgressor("step", "Calculating probabilities..." , 0, count, 1)

        # Make minimum distance 0.1 instead of 0 (for calculation)
        if blockgroups == "":
            cur = gp.updatecursor(r"in_memory\tbl", "NEAR_DIST = 0")
            row = cur.next()
            while row:
                row.NEAR_DIST = row.NEAR_DIST + .1
                cur.Updaterow(row)
                row = cur.next()
            del cur
            del row
        gp.SetProgressorPosition()

        # Process: Join origin attributes to near_table...
        desc = gp.describe(r"in_memory\bg")
        gp.JoinField(r"in_memory\tbl", "IN_FID", r"in_memory\bg", desc.OIDFieldName, "BID;" + str(sales))
        gp.SetProgressorPosition()
                    
        # Process: Join store attributes to near_table...
        desc = gp.describe(r"in_memory\st")
        gp.JoinField(r"in_memory\tbl", "NEAR_FID", r"in_memory\st", desc.OIDFieldName, "SID;" + str(store_name) + ";" + str(store_attr))
        gp.delete_management(r"in_memory\st")
        gp.SetProgressorPosition()        

        # Process: Add and Calculate tt_x_att Field ...
        gp.AddField_management(r"in_memory\tbl", "tt_x_att", "FLOAT", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
        if x == "":
            x = 2
        gp.CalculateField_management(r"in_memory\tbl", "tt_x_att","(1/ ([NEAR_DIST]^" + str(x) + ")) * [" + str(store_attr) + "]")
        gp.SetProgressorPosition()

#RESUME model calculations with tbl from EITHER OD Matrix or Near_Table 

    # Process: Summary Statistics (SUM of tt_x_att grouped by unique bg_stfid)...
    gp.Statistics_analysis(r"in_memory\tbl", r"in_memory\sumstats_tbl", "tt_x_att SUM", "BID")
    gp.SetProgressorPosition() 
       
    # Process: Summary Statistics(make list of store names)
    gp.Statistics_analysis(r"in_memory\tbl", r"in_memory\st_names", str(store_name) + " FIRST", str(store_name))
    gp.SetProgressorPosition()

    # Create search cursor to export and perform operations on tables with separate store names
    cur = gp.SearchCursor(r"in_memory\st_names")
    row = cur.Next()
    
    while row :
        storename = row.GetValue(store_name)
        whereclause = str(store_name) + " = '" + storename + "'"
        tblname = storename + "_tbl"

        # Process: Make Table View of unique store names...
        gp.tabletotable(r"in_memory\tbl", "in_memory", tblname, whereclause)
        gp.SetProgressorPosition()

        # Process: Join separate store tables to summary stats table
        gp.joinfield("in_memory" + os.sep + tblname, "BID", r"in_memory\sumstats_tbl", "BID", "SUM_tt_x_att")
        gp.SetProgressorPosition()
            
        # Process: Add and calculate probabilities in each store table (probability of each block group going to store x) ...
        gp.AddField_management("in_memory" + os.sep + tblname, str(storename) + "_prob" , "FLOAT", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
        gp.CalculateField_management("in_memory" + os.sep + tblname, str(storename) + "_prob", "[tt_x_att] / [SUM_tt_x_att]")
        gp.SetProgressorPosition()

        # Process: if sales projections are to be calculated, do so
        if sales == "":
            gp.joinfield(r"in_memory\bg", "BID", "in_memory" + os.sep + tblname, "BID", str(storename) + "_prob")
            gp.SetProgressorPosition()
        else:
            gp.AddField_management("in_memory" + os.sep + tblname, str(storename) + "_sales" , "FLOAT", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
            gp.CalculateField_management("in_memory" + os.sep + tblname, str(storename) + "_sales", "[" + str(storename) + "_prob] * [" + str(sales) +"]")
            gp.SetProgressorPosition()
            gp.joinfield(r"in_memory\bg", "BID", "in_memory" + os.sep + tblname, "BID", str(storename) + "_prob;" + str(storename) + "_sales")
            gp.SetProgressorPosition()

        # Add distance to stores	
        if distances.lower() == 'true':
            gp.AddField_management("in_memory" + os.sep + tblname, str(storename) + "_Total_" + cost , "FLOAT", "", "", "", "", "NULLABLE", "NON_REQUIRED", "")
            gp.CalculateField_management("in_memory" + os.sep + tblname, str(storename) + "_Total_" + cost, "[Total_" + cost + "]")
            gp.joinfield(r"in_memory\bg", "BID", "in_memory" + os.sep + tblname, "BID", str(storename) + "_Total_" + cost)

        # Delete in memory table to free up memory
        gp.delete_management(r"in_memory" + os.sep + tblname)
        
        # Determine the expected mean distance between input origin locations
        num1 = gp.getcount_management(r"in_memory\bg")
        num = int(num1.getoutput(0))
        expectedMeanDist = 1.0 / (2.0 * ((num / float(area))**0.5))
        
        # Generate surfaces if user desires
        if surfaces.lower() == 'true':
            gp.addmessage("Generating " + str(storename) + " Probability Surface")
            desc = gp.describe(studyarea)
            extent = desc.Extent
            gp.extent = extent
            if extent.xmax - extent.xmin > extent.ymax - extent.ymin:
                if (extent.ymax - extent.ymin)/250 > 400:
                    defcell = 400
                else:
                    defcell = (extent.ymax - extent.ymin)/250
            else:
                if (extent.xmax - extent.xmin)/250 > 400:
                    defcell = 400
                else:
                    defcell = (extent.xmax - extent.xmin)/250

            if gp.cellsize == "":
                gp.cellsize = defcell

            gp.mask = studyarea
            # Process: Create surface from store probability values (interpolate with Kriging)
            field = str(storename) + "_prob"
            output = outputgdb + "kriging_" + str(storename)
            props = "Spherical " + str(expectedMeanDist)
            gp.kriging_sa(r"in_memory\bg", field, output, props)
            gp.SingleOutputMapAlgebra_sa("Int([" + outputgdb + "kriging_" + str(storename) + "] * 100)",outputgdb + str(storename) + "_ProbSurface","#")
            gp.delete(outputgdb + "kriging_" + str(storename))
            gp.SetProgressorPosition()
           
            # Process: Create surface from store sales values (interpolate with Kriging)
            field = str(storename) + "_sales"
            output = outputgdb + "sales_kriging_" + str(storename)
            props = "Spherical " + str(expectedMeanDist)
            gp.kriging_sa(r"in_memory\bg", field, output, props)
            gp.SingleOutputMapAlgebra_sa("Int([" + outputgdb + "sales_kriging_" + str(storename) + "])",outputgdb + str(storename) + "_SalesSurface","#")
            gp.delete(outputgdb + "sales_kriging_" + str(storename))
            gp.SetProgressorPosition()

        gp.extent = ""
        
        # Exit the while loop
        row = cur.Next()
        
    # Delete in memory table to free up memory
    gp.delete_management(r"in_memory\tbl")
        
    if surfaces.lower() == 'true':
        gp.addmessage("Finished calculating probabilities and generating surfaces.")
    else:
        gp.addmessage("Finished calculating probabilities.")

############################################################################################################################################
############################################################################################################################################

    # setting progress bar for creating output feature class
    gp.SetProgressor("default", "Creating output feature class '" + fc_name + "'...")

    if blockgroups == "":
        gp.copyfeatures(r"in_memory\bg", outputgdb + str(fc_name))
        gp.delete_management(r"in_memory\bg")
    else:
        gp.featureclasstofeatureclass(blockgroups, "in_memory", "origins")
        desc = gp.describe(blockgroups)
        shapetype = desc.Shapetype
        if shapetype == "Polygon":
            gp.spatialjoin(r"in_memory\origins", r"in_memory\bg", outputgdb + str(fc_name), "", "", "", "CONTAINS")
        else:
            gp.spatialjoin(r"in_memory\origins", r"in_memory\bg", outputgdb + str(fc_name), "", "", "", "INTERSECTS")
        gp.delete_management(r"in_memory\bg")

    # Process: delete fields in fc_name
    deletefields = gp.listfields(outputgdb + str(fc_name), "*")
    for field in deletefields:
        if field.name == "BID" or field.name == str(sales) + "_1" or field.name == "Join_Count":
            gp.deletefield(outputgdb + str(fc_name), field.name)

    # Delete all in_memory data, since output has been written to gdb
    gp.workspace = "in_memory"
    fclist = gp.listfeatureclasses()
    for fc in fclist:
        gp.delete_management(fc)
        
    gp.addmessage("Finished creating output feature class '" + fc_name + "'.")    

############################################################################################################################################
############################################################################################################################################
   
    if marketareas.lower() == "surfaces" or marketareas.lower() == "both":
        # setting progress bar for creating market areas
        gp.SetProgressor("default", "Creating market areas from probability surfaces...")

        # set workspace to retrieve all probability surfaces
        gp.workspace = outfolder + "\\output.gdb"

        # Create list of all probability surface rasters
        rasterList = gp.listrasters("*ProbSurface")

        rasterNames = ""
        rasterNameLength = -1

        # Length of the longest store name needed for length of Highest_Prob field
        for raster in rasterList:
            rasterNames = rasterNames + raster + ";"
            length = len(str(raster))
            if length >= rasterNameLength:
                rasterNameLength = length

        newRasterNames = rasterNames.ljust(-1)[:-1]

        #Perform Highest Position tool to determine which store has the highest probability at each cell
        gp.highestposition(newRasterNames, outputgdb + "Surface_Markets")

        newRasterList = newRasterNames.split(";")

        #add field for indicating the store with the highest probability
        gp.addfield(outputgdb + "Surface_Markets", "Market" , "TEXT", "", "", rasterNameLength - 12)

        rows = gp.UpdateCursor(outputgdb + "Surface_Markets")
        row = rows.Next()

        while row:
            highestGrid = row.getvalue("VALUE")
            highestText = str(newRasterList[(int(highestGrid) - 1)])
            highestTextName = highestText.ljust(-12)[:-12]
            # Update Highest_Prob field with the name of the store
            row.SetValue("Market", highestTextName)
            rows.UpdateRow(row)
            row = rows.Next()
        del rows

    if marketareas.lower() == "origins" or marketareas.lower() == "both":
        # setting progress bar for creating market areas
        gp.SetProgressor("default", "Creating market areas from origins...")

        # set workspace to retrieve all probability surfaces
        gp.workspace = outfolder + os.sep + "output.gdb"

        # to determine the highest probability value
        fieldlist = gp.listfields(outputgdb + str(fc_name), "*prob")
        fieldNameLength = -1

        # Get the length of the longest store name
        for field in fieldlist:
            length = len(field.Name)
            if length >= fieldNameLength:
                fieldNameLength = length

        #add field for indicating the store with the highest sales value
        gp.addfield(fc_name, "Market" , "TEXT", "", "", fieldNameLength - 5)
            
        rows = gp.UpdateCursor(outputgdb + str(fc_name))
        row = rows.Next()

        while row:
            probValue = -9999.0
            probName = "NULL"
            # find the field with the highest probability value at that origin location
            for field in fieldlist:
                prob = row.getvalue(field.name)
                if prob >= probValue:
                    probValue = prob
                    probName = field.name
            #update the Highest_Prob field with the store name that has the highest probability at that origin location
            row.SetValue("Market", probName.ljust(-5)[:-5])
            rows.UpdateRow(row)
            row = rows.Next()
        del rows

    if marketareas.lower() != "none":
        gp.addmessage("Finished creating market areas.")

############################################################################################################################################
############################################################################################################################################

    # Add the output feature class to display, and in modelbuilder
    gp.setparameterastext(14,outfc)
    gp.setparameterastext(15,outmarkets)
    gp.setparameterastext(16,outpotential)
    
    gp.addmessage(" -- Process Complete -- ")

# Finish traceback Try-Except statement:
except:
    tb = sys.exc_info()[2]
    tbinfo = traceback.format_tb(tb)[0]
    pymsg = "PYTHON ERRORS:\nTraceback Info:\n" + tbinfo + "\nError Info:\n    " + \
            str(sys.exc_type)+ ": " + str(sys.exc_value) + "\n"
    AddPrintMessage(pymsg, 2)
    msgs = "GP ERRORS:\n" + gp.GetMessages(2) + "\n"
    AddPrintMessage(msgs, 2)        
