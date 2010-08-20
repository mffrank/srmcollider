#!/usr/bin/python
import os
import MySQLdb
import sys 
sys.path.append( '/home/ghost/hroest/code/' )
sys.path.append( '/home/ghost/software_libs/' )
sys.path.append( '/home/hroest/lib/' )
sys.path.append( '/home/hroest/msa/code/tppGhost' )
sys.path.append( '/home/hroest/msa/code' )
#import mzXMLreader
#import pepXMLReader
import time
from utils_h import utils
#import pipeline 
#db = MySQLdb.connect(read_default_file="~/hroest/.my.cnf")
db = MySQLdb.connect(read_default_file="~/.my.cnf")
c = db.cursor()
c2 = db.cursor()
import silver
import DDB 
import csv 
R = silver.Residues.Residues('mono')
import numpy

#with this method, I can do 
##method 2
# 22.2 per second, thus do 500k in 6 hours ==> using per peptide methods
##method 1
# 0.5 per second, thus do 500k in 240 hours ==> using per transition methods
class SRM_parameters(object):
    def __init__(self): 
        self.do_1vs = True #check only one charge state?
        self.do_vs1 = False #background only one charge state?
        self.ppm = True #measure q3 in ppm
        self.transition_table = 'hroest.srmTransitions_yeast'
        self.peptide_table = 'hroest.srmPeptides_yeast'
        self.q3_range = [300, 2000]
        self.ssrcalc_window = 2.0 / 2
        self.q1_window = 25.0 / 2.0
        self.q3_window = 10.0 / 2.0
        self.do_1_only = "and q1_charge = 2 and q3_charge = 1"
    def eval(self):
        self.query_add = ""
        self.query2_add = ""
        self.ppm_string = "Th"
        if self.do_1vs :
            self.query_add = "and q1_charge = 2"
            self.query1_add = self.do_1_only
        if self.do_vs1 : 
            self.query2_add = self.do_1_only
        if self.ppm: self.ppm_string = "PPM"
        self.experiment_type = """Experiment Type:
        check all four charge states [%s] vs all four charge states [%s] with
        thresholds of SSRCalc %s, Q1 %s (Th), Q3 %s (%s) and a range of %s to %s
        Da for the q3 transitions.  """ % ( not self.do_1vs, not self.do_vs1,
          self.ssrcalc_window*2,  self.q1_window*2, self.q3_window*2, 
          self.ppm_string, self.q3_range[0], self.q3_range[1])
    def get_q3_high(self, q1, q1_charge):
        q3_high = self.q3_range[1]
        if q3_high < 0: 
            if not self.query1_add == 'and q1_charge = 2 and q3_charge = 1':
                raise( 'relative q3_high not implemented for this combination')
            q3_high = q1 * q1_charge + q3_high
        return q3_high
    def get_q3_low(self):
        return self.q3_range[0]

par = SRM_parameters()
par.eval()
print par.experiment_type

#
###
#
#here we start
#make sure we only get unique peptides
cursor = db.cursor()
query = """
select parent_id, q1, q1_charge, ssrcalc
 from %s
 inner join
 ddb.peptide on peptide.id = %s.peptide_key
 inner join ddb.peptideOrganism on peptide.id = peptideOrganism.peptide_key 
 where genome_occurence = 1
 %s
""" % (par.peptide_table, par.peptide_table, par.query_add )
cursor.execute( query )
pepids = cursor.fetchall()
#
allpeps = {}
q3min_distr = []
q3min_distr_ppm = []
non_unique_count = 0
total_count = 0
start = time.time()
for i, pep in enumerate(pepids):
    if i % 1000 ==0: print i
    non_unique = {}
    non_unique_clash = {}
    non_unique_ppm = {}
    p_id, q1, q1_charge, ssrcalc = pep
    q3_high = par.get_q3_high(q1, q1_charge)
    q3_low = par.get_q3_low()
    #
    query1 = """
    select q1, ssrcalc, q3, srm_id
    from %(pep)s
    inner join %(trans)s
      on parent_id = parent_key
    where parent_id = %(parent_id)s
    and q3 > %(q3_low)s and q3 < %(q3_high)s         %(query_add)s
    """ % { 'parent_id' : p_id, 'q3_low' : q3_low,
           'q3_high' : q3_high, 'query_add' : par.query1_add,
           'pep' : par.peptide_table, 'trans' : par.transition_table }
    nr_transitions = cursor.execute( query1 )
    transitions = cursor.fetchall()
    #q1 = transitions[0][0]
    #ssrcalc = transitions[0][1]
    #
    query2 = """
    select q3
    from %(pep)s
    inner join %(trans)s
      on parent_id = parent_key
    where ssrcalc > %(ssrcalc)s - %(ssr_window)s 
        and ssrcalc < %(ssrcalc)s + %(ssr_window)s
    and q1 > %(q1)s - %(q1_window)s and q1 < %(q1)s + %(q1_window)s
    %(query_add)s
    """ % { 'q1' : q1, 'ssrcalc' : ssrcalc, 'parent_id' : p_id,
           'q3_low':q3_low,'q3_high':q3_high, 'q1_window' : par.q1_window,
           'query_add' : par.query2_add, 'ssr_window' : par.ssrcalc_window,
           'pep' : par.peptide_table, 'trans' : par.transition_table }
    #and parent_id != %(parent_id)d
    #and q3 > %(q3_low)s and q3 < %(q3_high)s
    tmp = cursor.execute( query2 )
    collisions = cursor.fetchall()
    #here we loop through all possible combinations of transitions and
    #potential collisions and check whether we really have a collision
    #TODO it might even be faster to switch the loops
    #TODO since the outer loop can be aborted as soon as a collision is found
    q3_window_used = par.q3_window
    for t in transitions:
        if par.ppm: q3_window_used = par.q3_window * 10**(-6) * t[2]
        min = q3_window_used
        for c in collisions:
            #here, its enough to know that one transition is colliding
            if abs( t[2] - c[0] ) <= min:
                min = abs( t[2] - c[0] )
                non_unique[ t[3] ] = t[2] - c[0]
                non_unique_ppm[ t[3] ] = (t[2] - c[0] ) * 10**6 / t[2]
    allpeps[ p_id ] = 1.0 - len( non_unique ) * 1.0  / nr_transitions
    for v in non_unique.values(): q3min_distr.append( v )
    for v in non_unique_ppm.values(): q3min_distr_ppm.append( v )
    non_unique_count += len( non_unique )
    total_count += len( transitions)
    end = time.time()




###########################################################################
#
# Analysis and printing


restable = 'hroest.testres'
c.execute( "create table %s (parent_key int, unique_transitions double) " % restable)
c.executemany( "insert into %s values " % restable + "values (%s,%s)", 
              allpeps.items() )


import pickle
common_filename = 'yeast_%s_%s_%d_%d_%dppm_range%sto%s' % (do_1vs, do_vs1, 
    ssrcalc_window*20,  q1_window*20, q3_window*20, q3_range[0], q3_range[1])
pickle.dump( q3min_distr, open(common_filename + '_q3min_distr.pkl' , 'w'))
pickle.dump( q3min_distr_ppm, open(common_filename + '_q3min_distr_ppm.pkl', 'w'))
pickle.dump( allpeps, open(common_filename + '_allpeps.pkl', 'w'))
pickle.dump( [non_unique_count, total_count], open(common_filename + '_count.pkl', 'w'))


dir = '/home/hroest/srm_clashes/results/pedro/'
fname = dir + "yeast_True_False_20_250_100ppm_range300to2000"
old_count = pickle.load( open(fname + "_allpeps.pkl"))

allpeps = pickle.load( open(fname + "_allpeps.pkl"))
pepids = [ (k,) for k in allpeps.keys()]

#p_id = 1
#{1L: 3830996L, 11L: 13837110L, 9L: 3881908L, 12L: 13837111L, 7L: 3881910L}
#{1L: 0.0024949999999535066, 11L: 0.0, 9L: -0.00089500000001407898, 12L: 0.0, 7L: -0.00089500000001407898}

#select * from hroest.srmTransitions_yeast inner join hroest.srmPeptides_yeast
#on parent_key = parent_id inner join  ddb.peptide on peptide_key = peptide.id
#where srm_id in (1, 3830996);



if True:
    #new method, clash distribution
    mydist = []
    for i, pep in enumerate(pepids):
        #this is the number of UNIQUE transitions
        p_id, q1, q1_charge = pep
        mydist.append( allpeps[p_id ] ) 
    len(mydist)
    h, n = numpy.histogram( mydist , 10)
    n = [nn * 100.0 + 5 for nn in n]
    h = [ hh *100.0 / len(mydist) for hh in h]
    import gnuplot
    reload( gnuplot )
    filename = common_filename
    gnu = gnuplot.Gnuplot.draw_boxes_from_data( [h,n], filename + '.eps',
      'Unique transitions per peptide / %' , 'Occurence / %', keep_data = True,
                                         tmp_csv = filename + '.csv' )
    cumh = get_cum_dist( h )
    filename = common_filename + "_cum"
    gnu = gnuplot.Gnuplot.draw_boxes_from_data( [cumh,n], filename + '.eps',
      'Unique transitions per peptide / %' , 'Cumulative Occurence / %')
    #gnu.add_to_body( "set yrange[0:30]" )
    #gnu.draw_boxes()
    #title = '(2+,1+) transitions, Background of 4 combinations [Range 300 to 1500 Da]' )


def get_cum_dist(original):
    cumulative = []
    cum  = 0
    for i, val in enumerate(original):
        cum += val
        cumulative.append(  cum )
    return cumulative

#print the q3min_distr
if True:
    len( [m for m in q3min_distr if m == 0.0 ]) * 1.0 / total_count
    h, n = numpy.histogram( q3min_distr, 500)
    reload( gnuplot )
    n = [nn * 10**3 for nn in n]
    filename = common_filename + '_q3distr' 
    gnu  = gnuplot.Gnuplot.draw_boxes_from_data( [h,n], filename + '.eps',
      'Q3 difference / 10^{-3} Th', 'Number of transitions', keep_data = True )
    #gnu.add_to_body( "set xrange[%s:%s]"  % (-1, 1) )
    #gnu.add_to_body( "set yrange[0:100]" )
    #gnu.draw_boxes()

#print the q3min_distr in ppm
if True:
    h, n = numpy.histogram( q3min_distr, 5000)
    reload( gnuplot )
    n = [nn * 10**3 for nn in n]
    filename = common_filename + '_q3distr_ppm' 
    gnu  = gnuplot.Gnuplot.draw_boxes_from_data( [h,n], filename + '.eps',
      'Q3 difference / ppm', 'Number of transitions', keep_data = True )
    #gnu.add_to_body( "set xrange[%s:%s]"  % (-0.1, 0.1) )
    #gnu.add_to_body( "set yrange[0:100]" )
    #gnu.draw_boxes()

#get a peptide length distribution
if True:
    cursor = db.cursor()
    query = """
    select parent_id, LENGTH( sequence )
     from %s
     inner join ddb.peptide on peptide.id = peptide_key
     %s
    """ % (peptide_table, query_add )
    cursor.execute( query )
    pepids = cursor.fetchall()
    len_distr  = [ [] for i in range(255) ]
    for zz in pepids:
        p_id, peplen = zz
        len_distr[ peplen ].append( allpeps[ p_id ]  )
    avg_unique_per_length = [ 0 for i in range(255) ]
    for i, l in enumerate(len_distr):
        if len(l) > 0:
            avg_unique_per_length[i] =    sum(l) / len(l) 
    h = avg_unique_per_length[6:26]
    h = [ hh *100.0 for hh in h]
    n = range(6,26)
    reload( gnuplot )
    filename = 'yeast_%s_%s_%d%d%d_range%sto%s_lendist' % (do_1vs, do_vs1, 
        ssrcalc_window*20,  q1_window*20, q3_window*20, q3_range[0], q3_range[1])
    gnu  = gnuplot.Gnuplot.draw_boxes_from_data( [h,n], filename + '.eps',
      'Peptide length', 'Average number of unique transitions per peptide / %', keep_data = True )
    gnu.add_to_body( "set xrange[%s:%s]"  % (4, 26) )
    gnu.add_to_body( "set yrange[0:100]" )
    gnu.draw_boxes()



reload(gnuplot)
c2.execute( "select floor(q1), count(*) from %s group by floor(q1)" % peptide_table)
bins = c2.fetchall()
filename = 'yeast_mzdist'
n = [nn[0] for nn in bins]
h = [hh[1] for hh in bins]
gnu  = gnuplot.Gnuplot.draw_points_from_data( [h,n], filename + '.eps',
  'Th', 'Occurence', keep_data = True)
gnu.add_to_body( "set xrange[400:]"   )
gnu.draw_points()


reload(gnuplot)
c2.execute( "select floor(ssrcalc), count(*) from %s group by floor(ssrcalc)" % peptide_table)
bins = c2.fetchall()
filename = 'yeast_rtdist'
n = [nn[0] for nn in bins]
h = [hh[1] for hh in bins]
gnu  = gnuplot.Gnuplot.draw_points_from_data( [h,n], filename + '.eps',
  'Retention time', 'Occurence', keep_data = True)
gnu.add_to_body( "set xrange[0:100]"   )
gnu.draw_points(2, True)



#print distribution in RT dimension
f = open( 'rtdist.csv', 'w' )
w = csv.writer(f,  delimiter='\t', quotechar='"', quoting=csv.QUOTE_MINIMAL) 
for i in range(50):
    w.writerow( [i - 50, rt_bin_len[ i - 50] ] )



#print distribution in Q1 dimension
f = open( 'mzdist.csv', 'w' )
w = csv.writer(f,  delimiter='\t', quotechar='"', quoting=csv.QUOTE_MINIMAL) 
for l in bins:
    w.writerow( [l[0], l[1] ] )

f.close()
