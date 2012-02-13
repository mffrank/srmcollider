import unittest
import time

import sys
sys.path.append( '.')
sys.path.append( '..')
sys.path.append( '../test/')
sys.path.append( './test/')
sys.path.append( '../external/')
import collider
import DDB 
import test_shared
from Residues import Residues

try:
    import c_getnonuis
except ImportError:
    print "=" * 75, """
Module c_getnonuis is not available. Please compile it if you want to use it.
""", "=" * 75

try:
    import c_rangetree
except ImportError:
    print "=" * 75, """
Module c_rangetree is not available. Please compile it if you want to use it.
""", "=" * 75

try:
    import c_integrated
except ImportError:
    print "=" * 75, """
Module c_integrated is not available. Please compile it if you want to use it.
""", "=" * 75

def mysort(x,y):
    if cmp(x[3], y[3]) == 0:
        return cmp(x[0], y[0])
    else: return cmp(x[3], y[3])

from test_shared import _get_unique_pepids
from test_shared import _get_all_collisions
from test_shared import get_non_UIS_from_transitions_old
from test_shared import get_non_UIS_from_transitions

def runcpp(self, pep, transitions, precursors):
    #first we run the C++ version
    st = time.time()
    for kk in range(10):
        tmp = c_getnonuis.calculate_collisions_per_peptide( 
            transitions, tuple(precursors), self.q3_low, self.q3_high, self.par.q3_window, self.par.ppm)
    ctime = (time.time() - st)/10.0
    return tmp, ctime

def runpy(self, pep, transitions, precursors):
    #now we run the pure Python version
    st = time.time()
    collisions = list(collider.SRMcollider._get_all_collisions_calculate_sub(
            collider.SRMcollider(), precursors, self.par, self.R, self.q3_low, self.q3_high))
    collisions_per_peptide = {}
    q3_window_used = self.par.q3_window
    for t in transitions:
        if self.par.ppm: q3_window_used = self.par.q3_window * 10**(-6) * t[0]
        for c in collisions:
            if abs( t[0] - c[0] ) <= q3_window_used:
                #gets all collisions
                if collisions_per_peptide.has_key(c[3]):
                    if not t[1] in collisions_per_peptide[c[3]]:
                        collisions_per_peptide[c[3]].append( t[1] )
                else: 
                    collisions_per_peptide[c[3]] = [ t[1] ] ; 
    oldtime = time.time() - st
    return collisions_per_peptide, oldtime

class Test_speed(unittest.TestCase):

    def setUp(self):
        try:
            import c_getnonuis
            self.transitions = test_shared.transitions_def1
            self.collisions = test_shared.collisions_def1
            self.pep1 = test_shared.peptide1
            self.pep2 = test_shared.peptide2

            self.transitions_12_between300_1500 = test_shared.transitions_12_between300_1500
            self.pep1_yseries = test_shared.pep1_yseries
            self.pep1_bseries = test_shared.pep1_bseries

            tuples = []
            tuples.append(self.pep1)
            tuples.append(self.pep2)
            self.tuples = tuple( tuples)

            self.R = Residues('mono')

            class Minimal: pass
            self.par = Minimal()
            self.par.q3_window = 4.0
            self.par.ppm = False
            self.q3_high = 1500
            self.q3_low = 300
            self.MAX_UIS = 5

            self.par.bions      =  True
            self.par.yions      =  True
            self.par.aions      =  False
            self.par.aMinusNH3  =  False
            self.par.bMinusH2O  =  False
            self.par.bMinusNH3  =  False
            self.par.bPlusH2O   =  False
            self.par.yMinusH2O  =  False
            self.par.yMinusNH3  =  False
            self.par.cions      =  False
            self.par.xions      =  False
            self.par.zions      =  False
            self.par.MMinusH2O  =  False
            self.par.MMinusNH3  =  False

        except ImportError:
            pass

    def test_calculatetrans1(self):
        print '\nTesting calculate_transitions 1'
        pep = test_shared.runpep1
        transitions = test_shared.runtransitions1
        precursors = test_shared.runprecursors1[240:300]
        transitions = tuple([ (t[0], i) for i,t in enumerate(transitions)])

        st = time.time()
        collisions = list(collider.SRMcollider._get_all_collisions_calculate_sub(
                collider.SRMcollider(), precursors, self.par, self.R, self.q3_low, self.q3_high))

        oldtime = time.time() - st
        st = time.time()
        tr_new = c_getnonuis.calculate_transitions_ch(tuple(precursors), [1,2], self.q3_low, self.q3_high)
        ctime = time.time() - st

        tr_new.sort(mysort)
        collisions.sort(mysort)

        self.assertEqual(len(tr_new), len(collisions))
        for o,n in zip(collisions, tr_new):
            for oo,nn in zip(o,n):
                self.assertTrue(oo - nn < 1e-5)

        print ctime, oldtime
        print "Speedup:", oldtime / ctime

    def test_calculatetrans2(self):
        print '\nTesting calculate_transitions 2'
        pep = test_shared.runpep2
        transitions = test_shared.runtransitions2
        precursors = test_shared.runprecursors2
        transitions = tuple([ (t[0], i) for i,t in enumerate(transitions)])

        st = time.time()
        collisions = list(collider.SRMcollider._get_all_collisions_calculate_sub(
                collider.SRMcollider(), precursors, self.par, self.R, self.q3_low, self.q3_high))

        oldtime = time.time() - st
        st = time.time()
        tr_new = c_getnonuis.calculate_transitions_ch(tuple(precursors), [1,2], self.q3_low, self.q3_high)
        ctime = time.time() - st

        tr_new.sort(mysort)
        collisions.sort(mysort)

        self.assertEqual(len(tr_new), len(collisions))
        for o,n in zip(collisions, tr_new):
            for oo,nn in zip(o,n):
                self.assertTrue(oo - nn < 1e-5)

        print ctime, oldtime
        print "Speedup:", oldtime / ctime

    def test_collperpeptide1(self):
        print '\nTesting collisions_per_peptide'

        pep = test_shared.runpep1
        transitions = test_shared.runtransitions1
        precursors = test_shared.runprecursors1
        transitions = tuple([ (t[0], i) for i,t in enumerate(transitions)])

        tmp, ctime = runcpp(self, pep, transitions, precursors)
        collisions_per_peptide, oldtime = runpy(self, pep, transitions, precursors)
        self.assertEqual(collisions_per_peptide, tmp )

        print ctime, oldtime
        print "Speedup:", oldtime / ctime

    def test_collperpeptide2(self):
        print '\nTesting collisions_per_peptide'

        pep = test_shared.runpep2
        transitions = test_shared.runtransitions2
        precursors = test_shared.runprecursors2
        transitions = tuple([ (t[0], i) for i,t in enumerate(transitions)])

        tmp, ctime = runcpp(self, pep, transitions, precursors)
        collisions_per_peptide, oldtime = runpy(self, pep, transitions, precursors)
        self.assertEqual(collisions_per_peptide, tmp )

        print ctime, oldtime
        print "Speedup:", oldtime / ctime
        
    def test_get_non_uis1(self):
        print '\nTesting non_uis_list'

        pep = test_shared.runpep1
        transitions = test_shared.runtransitions1
        precursors = test_shared.runprecursors1
        transitions = tuple([ (t[0], i) for i,t in enumerate(transitions)])
        collisions_per_peptide, ctime = runcpp(self, pep, transitions, precursors)

        MAX_UIS = self.MAX_UIS

        non_uis_list = [set() for i in range(MAX_UIS+1)]
        #here we calculate the UIS for this peptide with the given RT-range
        st = time.time()
        for pepc in collisions_per_peptide.values():
            for i in range(1,MAX_UIS+1):
                collider.get_non_uis(pepc, non_uis_list[i], i)
        oldtime = time.time() - st

        st = time.time()
        for kk in range(10):
            non_uis_list_new = [{} for i in range(MAX_UIS+1)]
            for order in range(1,MAX_UIS+1):
                non_uis_list_new[order] = c_getnonuis.get_non_uis(
                    collisions_per_peptide, order)

        non_uis_list_new = [set( res.keys() ) for res in non_uis_list_new]
        ctime = (time.time() - st)/10

        self.assertEqual(non_uis_list_new, non_uis_list)
        print ctime, oldtime
        print "Speedup:", oldtime / ctime

    def test_get_non_uis2(self):
        print '\nTesting non_uis_list'

        pep = test_shared.runpep2
        transitions = test_shared.runtransitions2
        precursors = test_shared.runprecursors2
        transitions = tuple([ (t[0], i) for i,t in enumerate(transitions)])
        collisions_per_peptide, ctime = runcpp(self, pep, transitions, precursors)

        MAX_UIS = self.MAX_UIS

        non_uis_list = [set() for i in range(MAX_UIS+1)]
        #here we calculate the UIS for this peptide with the given RT-range
        st = time.time()
        for pepc in collisions_per_peptide.values():
            for i in range(1,MAX_UIS+1):
                collider.get_non_uis(pepc, non_uis_list[i], i)
        oldtime = time.time() - st

        st = time.time()
        for kk in range(10):
            non_uis_list_new = [{} for i in range(MAX_UIS+1)]
            for order in range(1,MAX_UIS+1):
                non_uis_list_new[order] = c_getnonuis.get_non_uis(
                    collisions_per_peptide, order)

        non_uis_list_new = [set( res.keys() ) for res in non_uis_list_new]
        ctime = (time.time() - st)/10

        self.assertEqual(non_uis_list_new, non_uis_list)
        print ctime, oldtime
        print "Speedup:", oldtime / ctime

    def test_calculatetrans(self):
        print '\nTesting calculate_transitions'

        myprecursors = ((500, 'PEPTIDE', 1, 1, 0), (400, 'CEPC[160]IDM[147]E', 2, 2, 0))
        st = time.time()
        for i in range(100000):
            tr_new = c_getnonuis.calculate_transitions_ch(myprecursors, [1,2], self.q3_low, self.q3_high)
        ctime = time.time() - st
        st = time.time()
        coll = collider.SRMcollider()
        for i in range(100000):
            tr_old = list(collider.SRMcollider._get_all_collisions_calculate_sub(
                        coll, myprecursors, self.par, self.R, self.q3_low, self.q3_high))
        oldtime = time.time() - st

        tr_new.sort(mysort)
        tr_old.sort(mysort)

        self.assertEqual(len(tr_new), len(tr_old) )
        self.assertEqual(tr_new, tr_old)
        print ctime, oldtime
        print "Speedup:", oldtime / ctime

    def test_getmintrans1(self):
        print '\nTesting _getMinNeededTransitions'
        pep = test_shared.runpep1
        transitions = test_shared.runtransitions1
        precursors = test_shared.runprecursors1
        transitions = tuple([ (t[0], i) for i,t in enumerate(transitions)])
        par = self.par
        q3_high = self.q3_high
        q3_low = self.q3_low
        R = self.R
        par.max_uis = 15

        collisions = list(collider.SRMcollider._get_all_collisions_calculate_sub(
                collider.SRMcollider(), precursors, par, R, q3_low, q3_high))
        st = time.time()
        m = collider.SRMcollider()._getMinNeededTransitions(par, transitions, collisions)
        oldtime = time.time() - st

        import c_integrated
        st = time.time()
        m = c_integrated.getMinNeededTransitions(transitions, tuple(precursors), 
            par.max_uis, par.q3_window, par.ppm, par)
        ctime = time.time() - st

        print ctime, oldtime
        print "Speedup:", oldtime / ctime

class Test_speed_integrated(unittest.TestCase):

    def setUp(self):
        self.limit = 100
        self.limit_large = 100
        self.limit = 300
        self.limit_large = 600
        try:
            import MySQLdb
            import time
            import sys 
            sys.path.append( '/home/hroest/srm_clashes/code' )
            sys.path.append( '/home/hroest/lib/' )
            sys.path.append( '/home/hroest/projects/' )
            sys.path.append( '/home/hroest/projects/srm_clashes/code' )
            #db_l = MySQLdb.connect(read_default_file="~/.my.cnf.local")
            db = MySQLdb.connect(read_default_file="~/.my.cnf.orl")
            cursor = db.cursor()
            #cursor_l = db_l.cursor()
            #cursor = cursor_l
            import collider
            import progress
            import hlib
            import copy
            #Run the collider
            ###########################################################################
            par = collider.SRM_parameters()
            par.q1_window = 20 / 2.0 #UIS paper = 1.2
            par.q3_window = 20.0 / 2.0 #UIS paper = 2.0
            par.q1_window = 1.2 / 2.0 #UIS paper = 1.2
            par.q3_window = 2.0 / 2.0 #UIS paper = 2.0
            #12 = 90%TPR, 8 = 80%TPR 
            par.ssrcalc_window = 4 / 2.0 #for paola do 9999 and 4
            par.ssrcalc_window = 9999 / 2.0 #for paola do 9999 and 4
            par.ppm = False
            par.considerIsotopes = True
            par.isotopes_up_to = 3
            par.do_1vs = False
            par.dontdo2p2f = False #important for precursor to work
            par.transition_table = 'hroest.srmTransitions_human'
            par.peptide_table = 'hroest.srmPeptides_human'
            par.transition_table = 'hroest.srmTransitions_yeast'
            par.peptide_table = 'hroest.srmPeptides_yeast'
            par.max_uis = 5 #turn off uis if set to 0
            par.q3_range = [400, 1400]
            par.yions = True
            par.bions = True
            par.eval()
            #print par.experiment_type

            self.mycollider = collider.SRMcollider()

            self.par = par
            self.min_q1 = 440
            self.max_q1 = 450

            start = time.time()
            cursor.execute( """
            #select modified_sequence, peptide_key, parent_id, q1_charge, q1, ssrcalc, isotope_nr, 0, 0
            #select modified_sequence, transition_group, parent_id, q1_charge, q1, ssrcalc, modifications, missed_cleavages, isotopically_modified
            select modified_sequence, transition_group, parent_id, q1_charge, q1, ssrcalc, isotope_nr, 0, 0
            from %s where q1 between %s and %s
                           """ % (par.peptide_table, self.min_q1 - par.q1_window, self.max_q1 + par.q1_window) )

            #print "finished query execution: ", time.time() - start
            self.alltuples =  list(cursor.fetchall() )
            self.cursor = cursor

        except Exception as inst:
            print "something went wrong"
            print inst

    def test_integrated_range(self):

        # currently deactivated because we set up the rangetree in a completely new way
        return True
        try:
            print "Trying test integrated range"
            par = self.par
            cursor = self.cursor

            from random import shuffle
            start = time.time()
            #shuffle(self.alltuples)
            #print "finished query fetch: ", time.time() - start

            mypepids = [
                        {
                            'mod_sequence'  :  r[0],
                            'peptide_key' :r[1],
                            'parent_id' :  r[2],
                            'q1_charge' :  r[3],
                            'q1' :         r[4],
                            'ssrcalc' :    r[5],
                            'transition_group' :  r[2],
                        }
                        for r in self.alltuples
                if r[3] == 2 #charge is 2
                and r[6] == 0 #isotope is 0
                and r[4] >= self.min_q1
                and r[4] < self.max_q1
            ]

            parentid_lookup = [ [ r[2], (r[4], r[0], r[1]) ] 
                        for r in self.alltuples
                #if r[3] == 2 and r[6] == 0
            ]
            parentid_lookup  = dict(parentid_lookup)
            #print "finished python lookups: ", time.time() - start

            mystart = time.time()
            #c_rangetree.create_tree(alltuples[:100000])
            #print "building tree with : %s nodes " % len(self.alltuples)
            c_rangetree.create_tree(tuple(self.alltuples))
            #print "finished build tree : ", time.time() - start
            #print "tree time ", time.time() - mystart

            self.mycollider.pepids = mypepids
            MAX_UIS = 5
            newtime = 0; oldtime = 0; ctime = 0
            oldsql = 0; newsql = 0
            alllocaltime = 0
            localprecursor = 0
            c_fromprecursortime = 0
            #progressm = progress.ProgressMeter(total=len(self.pepids), unit='peptides')
            prepare  = []
            self._cursor = False
            print '\n'*2
            print "old = use fast SQL to get precursors, use C++ code to get collperpep"
            print "new = use rangetree to get precursors, use C++ code to get collperpep"
            print "i\tnew_prec_tot\trangetree\tnewcollper\ttotalnew\t>>\ttotalold\tspeedup"
            self.mycollider.pepids = self.mycollider.pepids[:self.limit_large]
            for kk, pep in enumerate(self.mycollider.pepids):
                ii = kk + 1
                p_id = pep['parent_id']
                q1 = pep['q1']
                ssrcalc = pep['ssrcalc']
                q3_low, q3_high = par.get_q3range_transitions()
                #
                #new way to calculate the precursors
                mystart = time.time()
                transitions = c_getnonuis.calculate_transitions_ch(
                    ((q1, pep['mod_sequence'], p_id),), [1,2], q3_low, q3_high)
                #fake some srm_id for the transitions
                transitions = tuple([ (t[0], i) for i,t in enumerate(transitions)])
                q1_low = q1 - par.q1_window 
                q1_high = q1 + par.q1_window
                innerstart = time.time()
                isotope_correction = par.isotopes_up_to * Residues.mass_diffC13 / min(par.parent_charges)
                #correct rounding errors, s.t. we get the same results as before!
                ssrcalc_low = ssrcalc - par.ssrcalc_window + 0.001
                ssrcalc_high = ssrcalc + par.ssrcalc_window - 0.001
                precursor_ids = tuple(c_rangetree.query_tree( q1 - par.q1_window, ssrcalc_low, 
                    q1 + par.q1_window,  ssrcalc_high, par.isotopes_up_to, isotope_correction))
                precursors = tuple([parentid_lookup[myid[0]] for myid in precursor_ids
                                    #dont select myself 
                                       if parentid_lookup[myid[0]][2]  != pep['transition_group']])


                alllocaltime += time.time() - mystart
                #
                #now calculate coll per peptide the new way
                mystart = time.time()
                collisions_per_peptide = c_getnonuis.calculate_collisions_per_peptide( 
                    transitions, precursors, q3_low, q3_high, par.q3_window, par.ppm)
                non_uis_list = [{} for i in range(MAX_UIS+1)]
                for order in range(1,MAX_UIS+1):
                    non_uis_list[order] = c_getnonuis.get_non_uis(
                        collisions_per_peptide, order)
                c_fromprecursortime += time.time() - mystart
                precursor_new = precursors
                non_uis_list_new = [set(kk.keys()) for kk in non_uis_list]
                non_uis_list_len = [len(kk) for kk in non_uis_list]
                transitions_before = transitions

                ###################################
                #old way to calculate the precursors
                mystart = time.time()
                #transitions = self.mycollider._get_all_transitions(par, pep, cursor)
                transitions = collider.calculate_transitions_ch(
                    ((q1, pep['mod_sequence'], p_id),), [1], q3_low, q3_high)
                #fake some srm_id for the transitions
                transitions = tuple([ (t[0], i) for i,t in enumerate(transitions)])
                nr_transitions = len( transitions )
                if nr_transitions == 0: continue #no transitions in this window
                transitions = transitions_before
                par.query2_add = ' and isotope_nr = 0 ' # due to the new handling of isotopes
                precursors = self.mycollider._get_all_precursors(par, pep, cursor)
                par.query2_add = '' # due to the new handling of isotopes
                newsql += time.time() - mystart
                #
                #now calculate coll per peptide the new way
                mystart = time.time()
                collisions_per_peptide = c_getnonuis.calculate_collisions_per_peptide( 
                    transitions, precursors, q3_low, q3_high, par.q3_window, par.ppm)
                non_uis_list = [ {} for i in range(MAX_UIS+1)]
                for order in range(1,MAX_UIS+1):
                    non_uis_list[order] = c_getnonuis.get_non_uis(
                        collisions_per_peptide, order)
                ctime += time.time() - mystart
                non_uis_list_len_old = [len(kk) for kk in non_uis_list]

                print len(precursors), len(precursor_new) 
                self.assertEqual( len(precursors), len(precursor_new) )
                self.assertEqual( non_uis_list_len_old , non_uis_list_len) 

                # 1. row is sequence
                # 2. row is the total time for the rangetree query 
                # 3. row is the time of the rangetree query which actually
                #    queries the rangetree and the rest of the time we spend
                #    filtering out the peptide_key of the current peptide
                # 4. row is the time to calculate the collisions per peptide
                #    from the precursors
                # 5. is row 2 and 4 combined
                # >>>
                # 6. is the time to get the precursors by querying the db plus
                #    the time to get collisions per peptide from the C++ code
                mys =  "%s\t%0.2fms\t\t%0.2fms\t\t%0.2fms\t\t%0.2fms\t\t>>\t%0.2fms\t%0.2f" % \
                (ii, alllocaltime *1000/ ii, \
                        localprecursor*1000/ii, c_fromprecursortime*1000/ii, 
                 #in the last speedtest, the new version is ctime+newsql
                 #this should correspond to the OLD version here
                 #allnew
                 (alllocaltime + c_fromprecursortime)*1000/ii, 
                 #(alllocaltime + c_fromprecursortime)*1000/ii, 
                 #
                 # >>
                 #
                 (ctime + newsql)*1000/ii, 
                 #(c_fromprecursortime + newsql)*1000/ii, 
                 (ctime + newsql)/ (alllocaltime + c_fromprecursortime) )
                #start a new line for each output?
                #mys += '\t%s\t%s' % ( len(precursors), len(precursor_new) )
                if False: mys += '\n'

                self.ESC = chr(27)
                sys.stdout.write(self.ESC + '[2K')
                if self._cursor:
                    sys.stdout.write(self.ESC + '[u')
                self._cursor = True
                sys.stdout.write(self.ESC + '[s')
                sys.stdout.write(mys)
                sys.stdout.flush()


        except Exception as inst:
            print "something went wrong"
            print inst

    def test_integrated_integrated(self):
        """ Here we are testing the fully integrated solution of storing all
        precursors in a C++ range tree and never passing them to Python.
        """

        try:
            print "Trying test integrated"
            par = self.par
            cursor = self.cursor

            from random import shuffle
            start = time.time()
            shuffle(self.alltuples)
            print "finished query fetch: ", time.time() - start, " with nr. tuples", len(self.alltuples)

            mypepids = [
                        {
                            'mod_sequence'  :  r[0],
                            'peptide_key' :r[1],
                            'parent_id' :  r[2],
                            'q1_charge' :  r[3],
                            'q1' :         r[4],
                            'ssrcalc' :    r[5],
                        }
                        for r in self.alltuples
                if r[3] == 2 #charge is 2
                and r[6] == 0 #isotope is 0
                and r[4] >= self.min_q1
                and r[4] < self.max_q1
            ]

            parentid_lookup = [ [ r[2], (r[4], r[0], r[1]) ] 
                        for r in self.alltuples
                #if r[3] == 2 and r[6] == 0
            ]
            parentid_lookup  = dict(parentid_lookup)

            mystart = time.time()
            c_rangetree.create_tree(tuple(self.alltuples))
            c_integrated.create_tree(tuple(self.alltuples))

            self.mycollider.pepids = mypepids
            MAX_UIS = 5
            newtime = 0; oldtime = 0; ctime = 0
            oldsql = 0; newsql = 0
            alllocaltime = 0
            localprecursor = 0
            transitiontime = 0
            c_fromprecursortime = 0
            #progressm = progress.ProgressMeter(total=len(self.pepids), unit='peptides')
            prepare  = []
            self._cursor = False
            print "Running experiment ", par.get_common_filename()
            print '\n'*2
            print "old = use rangetree to get precursors, use C++ code to get collperpep"
            print "new = use rangetree to get precursors, use single C++ code to get collperpep"
            print "i\tnew_prec_tot\tnew\t\told\t\t>>\tspeedup"
            self.mycollider.pepids = self.mycollider.pepids[:self.limit_large]
            for kk, pep in enumerate(self.mycollider.pepids):
                ii = kk + 1
                p_id = pep['parent_id']
                q1 = pep['q1']
                ssrcalc = pep['ssrcalc']
                q3_low, q3_high = par.get_q3range_transitions()
                #
                #new way to calculate the precursors
                mystart = time.time()
                transitions = c_getnonuis.calculate_transitions_ch(
                    ((q1, pep['mod_sequence'], p_id),), [1,2], q3_low, q3_high)
                nr_transitions = len( transitions )
                #fake some srm_id for the transitions
                transitions = tuple([ (t[0], i) for i,t in enumerate(transitions)])
                q1_low = q1 - par.q1_window 
                q1_high = q1 + par.q1_window
                innerstart = time.time()
                #correct rounding errors, s.t. we get the same results as before!
                ssrcalc_low = ssrcalc - par.ssrcalc_window + 0.001
                ssrcalc_high = ssrcalc + par.ssrcalc_window - 0.001
                transitiontime += time.time() - mystart
                isotope_correction = par.isotopes_up_to * Residues.mass_diffC13 / min(par.parent_charges)

                ###################################
                #new way to calculate non_uislist 
                #start out from transitions, get non_uislist
                mystart = time.time()
                newresult = c_integrated.wrap_all_magic(transitions, q1_low, ssrcalc_low,
                    q1_high,  ssrcalc_high, pep['peptide_key'],
                    min(MAX_UIS,nr_transitions) , par.q3_window, #q3_low, q3_high,
                    par.ppm, par.isotopes_up_to, isotope_correction, par)
                newtime += time.time() - mystart


                mystart = time.time()
                ###################################
                #old way to calculate non_uislist
                #get precursors
                #get collperpep
                #get non_uislist
                precursor_ids = tuple(c_rangetree.query_tree( q1_low, ssrcalc_low, 
                    q1_high,  ssrcalc_high, par.isotopes_up_to, isotope_correction)) 
                precursors = tuple([parentid_lookup[myid[0]] for myid in precursor_ids
                                    #dont select myself 
                                   if parentid_lookup[myid[0]][2]  != pep['peptide_key']])
                collisions_per_peptide = c_getnonuis.calculate_collisions_per_peptide( 
                    transitions, precursors, q3_low, q3_high, par.q3_window, par.ppm)
                non_uis_list = [{} for i in range(MAX_UIS+1)]
                for order in range(1,MAX_UIS+1):
                    non_uis_list[order] = c_getnonuis.get_non_uis(
                        collisions_per_peptide, order)

                oldtime += time.time() - mystart

                non_uis_list_new = [set(kk.keys()) for kk in non_uis_list]
                non_uis_list_len = [len(kk) for kk in non_uis_list_new[1:]]

                self.assertEqual( newresult , non_uis_list_len) 

                mys =  "%s\t%0.2fms\t\t%0.2fms\t\t%0.2fms\t\t>>\t%0.2f" % \
                (ii, transitiontime *1000/ ii, 
                        newtime*1000/ii, oldtime*1000/ii,
                oldtime *1.0 / newtime)
                #start a new line for each output?
                #mys += '\t%s\t%s' % ( len(precursors), len(precursor_new) )
                if False: mys += '\n'

                self.ESC = chr(27)
                sys.stdout.write(self.ESC + '[2K')
                if self._cursor:
                    sys.stdout.write(self.ESC + '[u')
                self._cursor = True
                sys.stdout.write(self.ESC + '[s')
                sys.stdout.write(mys)
                sys.stdout.flush()


        except Exception as inst:
            print "something went wrong"
            print inst

    def test_integrated_mysql(self):
            """ Here we are testing the old (querying the transitions database as
            well as the precursor database) and the new way (only query the
            precursor database and calculate the transitions on the fly) way of
            calculating the collisions.
            """

            print "Trying test mysql"
            par = self.par
            cursor = self.cursor

            mycollider = collider.SRMcollider()
            mypepids = _get_unique_pepids(par, cursor)
            self.mycollider.pepids = mypepids
            self.mycollider.calcinner = 0
            from random import shuffle
            shuffle( self.mycollider.pepids )
            self.mycollider.pepids = self.mycollider.pepids[:self.limit]

            MAX_UIS = 5
            c_newuistime = 0; oldtime = 0; c_fromprecursortime = 0
            oldsql = 0; newsql = 0
            oldcalctime = 0; localsql = 0
            self._cursor = False
            print '\n'*2
            print "oldtime = get UIS from collisions and transitions (getting all collisions from the transitions db)"
            print "cuis + oldsql = as oldtime but calculate UIS in C++"
            print "newsql = only get the precursors from the db and calculate collisions in Python"
            print "ctime + newsql = only get the precursors from the db and calculate collisions in C++"
            print "new = use fast SQL and C++ code"
            print "old = use slow SQL and Python code"
            print "i\toldtime\tcuis+oldsql\tnewsql\tctime+newsql\t>>>\toldsql\tnewsql\tunused\t...\tspeedup"
            for kk, pep in enumerate(self.mycollider.pepids):
                ii = kk + 1
                p_id = pep['parent_id']
                q1 = pep['q1']
                q3_low, q3_high = par.get_q3range_transitions()
                transitions = collider.calculate_transitions_ch(
                    ((q1, pep['mod_sequence'], p_id),), [1], q3_low, q3_high)
                #fake some srm_id for the transitions
                transitions = tuple([ (t[0], i) for i,t in enumerate(transitions)])
                ##### transitions = self.mycollider._get_all_transitions(par, pep, cursor)
                nr_transitions = len( transitions )
                if nr_transitions == 0: continue #no transitions in this window
                #
                mystart = time.time()
                collisions = list(self.mycollider._get_all_collisions_calculate_new(par, pep, cursor))
                oldcolllen = len(collisions)
                oldcalctime += time.time() - mystart
                #
                mystart = time.time()
                collisions = _get_all_collisions(mycollider, par, pep, cursor, transitions = transitions)
                oldcsqllen = len(collisions)
                oldsql += time.time() - mystart
                #
                par.query2_add = ' and isotope_nr = 0 ' # due to the new handling of isotopes
                mystart = time.time()
                self.mycollider.mysqlnewtime= 0
                precursors = self.mycollider._get_all_precursors(par, pep, cursor)
                newsql += time.time() - mystart
                #
                mystart = time.time()
                #precursors = self.mycollider._get_all_precursors(par, pep, cursor_l)
                localsql += time.time() - mystart
                par.query2_add = '' # due to the new handling of isotopes
                #
                mystart = time.time()
                non_uis_list = get_non_UIS_from_transitions(transitions, 
                                            tuple(collisions), par, MAX_UIS)
                cnewuis = non_uis_list
                c_newuistime += time.time() - mystart
                #
                mystart = time.time()
                non_uis_list = get_non_UIS_from_transitions_old(transitions, 
                                            collisions, par, MAX_UIS)
                oldnonuislist = non_uis_list
                oldtime += time.time() - mystart
                #
                mystart = time.time()
                q3_low, q3_high = par.get_q3range_transitions()
                collisions_per_peptide = c_getnonuis.calculate_collisions_per_peptide( 
                    transitions, precursors, q3_low, q3_high, par.q3_window, par.ppm)
                non_uis_list = [ {} for i in range(MAX_UIS+1)]
                for order in range(1,MAX_UIS+1):
                    non_uis_list[order] = c_getnonuis.get_non_uis(
                        collisions_per_peptide, order)
                c_fromprecursortime += time.time() - mystart
                #print ii, len(collisions), oldtime + oldsql , newtime + oldsql, ctime + newsql, ">>>>" , oldsql, newsql

                newl = [len(n) for n in non_uis_list]
                self.assertEqual(newl, [len(o) for o in cnewuis])
                self.assertEqual(newl, [len(o) for o in oldnonuislist])

                non_uis_list = [set(k.keys()) for k in non_uis_list]
                cnewuis = [set(k.keys()) for k in cnewuis]

                self.assertEqual(non_uis_list, cnewuis)
                self.assertEqual(non_uis_list, oldnonuislist)

                mys =  "%s\t%0.fms\t%0.fms\t\t%0.fms\t%0.2fms\t\t>>>\t%0.fms\t%0.2fms\t%0.2f\t...\t%0.2f" % \
                (ii, 
                 (oldtime + oldsql)*1000/ii, 
                 (c_newuistime+oldsql)*1000/ii,
                 (oldcalctime + newsql + oldtime)*1000/ii, 
                 (c_fromprecursortime + newsql)*1000/ii, 
                 #(c_fromprecursortime + localsql)*1000/ii,
                 #42.42,

                 oldsql*1000/ii, 
                 newsql*1000/ii,
                 #localsql*1000/ii,
                 42.42,

                 #oldtime / c_newuistime
                 (oldtime + oldsql) / (c_fromprecursortime + newsql)
                )

                self.ESC = chr(27)
                sys.stdout.write(self.ESC + '[2K')
                if self._cursor:
                    sys.stdout.write(self.ESC + '[u')
                self._cursor = True
                sys.stdout.write(self.ESC + '[s')
                sys.stdout.write(mys)
                sys.stdout.flush()

if __name__ == '__main__':
    unittest.main()
