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

    # Establish 'step' progressor settings
    gp.SetProgressor("step", "Checking inputs against parameter requirements..." , 0, 9, 1) 

    # Process: Make output file gdb
    gp.createfilegdb(outfolder, "output.gdb")
    outputgdb = outfolder + "\\output.gdb" + os.sep
    gp.SetProgressorPosition()

    ingdb = outfolder + os.sep
#    cur = gp.SearchCursor(stores)
#    row = cur.Next()

    # Process: Summary Statistics(make list of store names)
    gp.Statistics_analysis(stores, r"in_memory\st_names", str(store_name) + " FIRST", str(store_name))
    gp.SetProgressorPosition()

    # Create search cursor to export and perform operations on tables with separate store names
    cur = gp.SearchCursor(r"in_memory\st_names")
    row = cur.Next()
    
    while row :
        storename = row.GetValue(store_name)
        # Generate surfaces if user desires
        if str(storename) in ["a","d"]:
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
            gp.kriging_sa(ingdb + fc_name, field, output, props)
            gp.SingleOutputMapAlgebra_sa("Int([" + outputgdb + "kriging_" + str(storename) + "] * 100)",outputgdb + str(storename) + "_ProbSurface","#")
            gp.delete(outputgdb + "kriging_" + str(storename))
            gp.SetProgressorPosition()
           
            # Process: Create surface from store sales values (interpolate with Kriging)
            field = str(storename) + "_sales"
            output = outputgdb + "sales_kriging_" + str(storename)
            props = "Spherical " + str(expectedMeanDist)
            gp.kriging_sa(ingdb + fc_name, field, output, props)
            gp.SingleOutputMapAlgebra_sa("Int([" + outputgdb + "sales_kriging_" + str(storename) + "])",outputgdb + str(storename) + "_SalesSurface","#")
            gp.delete(outputgdb + "sales_kriging_" + str(storename))
            gp.SetProgressorPosition()
            
            row = cur.Next()
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
