#!/usr/bin/python
# -*- coding: utf-8  -*-

"""
 *
 * Program       : SRMCollider
 * Author        : Hannes Roest <roest@imsb.biol.ethz.ch>
 * Date          : 05.02.2011 
 *
 *
 * Copyright (C) 2011 Hannes Roest
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Lesser General Public
 * License as published by the Free Software Foundation; either
 * version 2.1 of the License, or (at your option) any later version.
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public
 * License along with this library; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307, USA
 *
"""

import sys, os, time
import progress
import DDB
import Residues

from SRM_parameters import *

class SRMcollider(object):

    def _get_all_precursors(self, par, pep, cursor, 
         values="q1, modified_sequence, transition_group, q1_charge, isotopically_modified", 
         bysequence=False):
        vdict = { 'q1' : pep['q1'], 'ssrcalc' : pep['ssrcalc'],
                'transition_group' : pep['transition_group'], 'q1_window' : par.q1_window,
                'query_add' : par.query2_add, 'ssr_window' : par.ssrcalc_window,
                'pep' : par.peptide_table, 'values' : values, 
                'pepseq' : pep['mod_sequence']}
        if bysequence: selectby = "and %(pep)s.modified_sequence != '%(pepseq)s'" % vdict
        else: selectby = "and %(pep)s.transition_group != %(transition_group)d" % vdict
        vdict['selectby'] = selectby
        #
        # calculate how much lower we need to select to get all potential isotopes:
        #  to get all isotopes = lower_winow - nr_isotopes_to_consider * mass_difference_of_C13 / minimal_parent_charge
        R = Residues.Residues('mono')
        vdict['isotope_correction'] = par.isotopes_up_to * R.mass_diffC13 / min(par.parent_charges)
        query2 = """
        select %(values)s
        from %(pep)s
        where ssrcalc > %(ssrcalc)s - %(ssr_window)s 
            and ssrcalc < %(ssrcalc)s + %(ssr_window)s
        and q1 > %(q1)s - %(q1_window)s - %(isotope_correction)s and q1 < %(q1)s + %(q1_window)s
        %(selectby)s
        %(query_add)s
        """ % vdict
        if par.print_query: print query2
        #print query2
        cursor.execute( query2 )
        # now filter out all the precursors that do not have an isotope that falls in here
        # -- need to assure that r[0] is the q1 and r[3] the q1_charge
        # if the mass of the peptide or that of any of its isotopes is within
        # the window, we will use it.
        result = cursor.fetchall()
        assert(values[:50] == "q1, modified_sequence, transition_group, q1_charge")
        new_result = []
        for r in result:
          append = False
          ch = r[3]
          for iso in range(par.isotopes_up_to+1):
            if (r[0] + (R.mass_diffC13 * iso)/ch > pep['q1'] - par.q1_window and 
                r[0] + (R.mass_diffC13 * iso)/ch < pep['q1'] + par.q1_window): append=True
          if(append): new_result.append(r)
        return tuple(new_result)

    # calculates all fragments of the peptide in Python and compares them to
    # the fragments of the precursors
    def _get_all_collisions_calculate_new(self, par, pep, cursor, 
      values="q1, modified_sequence, transition_group, q1_charge, transition_group"):
        R = Residues.Residues('mono')
        RN15 = Residues.Residues('mono')
        RN15.recalculate_monisotopic_data_for_N15()
        q3_low, q3_high = par.get_q3range_collisions()
        return self._get_all_collisions_calculate_sub(
            self._get_all_precursors(par, pep, cursor, values=values), 
            par, R, q3_low, q3_high, RN15)


    def _get_all_collisions_calculate_sub(self, precursors, par, R, q3_low, q3_high, RN15=None):
        for c in precursors:
            q1 = c[0]
            peptide_key = c[2]
            peptide = DDB.Peptide()
            peptide.set_sequence(c[1])
            peptide.charge = c[3]
            if c[4] == Residues.NOISOTOPEMODIFICATION:
              R_used = R
            elif c[4] == Residues.N15_ISOTOPEMODIFICATION:
              R_used = RN15
            peptide.create_fragmentation_pattern( R_used, 
                aions      =  par.aions    ,
                aMinusNH3  =  par.aMinusNH3,
                bions      =  par.bions    ,
                bMinusH2O  =  par.bMinusH2O,
                bMinusNH3  =  par.bMinusNH3,
                bPlusH2O   =  par.bPlusH2O ,
                yions      =  par.yions    ,
                yMinusH2O  =  par.yMinusH2O,
                yMinusNH3  =  par.yMinusNH3,
                cions      =  par.cions    ,
                xions      =  par.xions    ,
                zions      =  par.zions    ,
                MMinusH2O  =  par.MMinusH2O,
                MMinusNH3  =  par.MMinusNH3)
            for ch in [1,2]:
                for pred in peptide.allseries:
                    q3 = ( pred + (ch -1)*R.mass_H)/ch
                    #if q3 < q3_low or q3 > q3_high: continue
                    yield (q3, q1, 0, peptide_key)

    # calculates the minimally needed number of transitions for a peptide to be
    # uniquely identifiable in a background given a list of transitions sorted
    # by priority (intensity)
    def _getMinNeededTransitions(self, par, transitions, collisions):
        nr_transitions = len( transitions )
        nr_used_tr = min(par.max_uis+1, nr_transitions)
        mytransitions = transitions[:nr_used_tr]
        collisions_per_peptide = {}
        q3_window_used = par.q3_window
        for t in mytransitions:
            if par.ppm: q3_window_used = par.q3_window * 10**(-6) * t[0]
            for c in collisions:
                if abs( t[0] - c[0] ) <= q3_window_used:
                    #gets all collisions
                    if collisions_per_peptide.has_key(c[3]):
                        if not t[1] in collisions_per_peptide[c[3]]:
                            collisions_per_peptide[c[3]].append( t[1] )
                    else: collisions_per_peptide[c[3]] = [ t[1] ] 
        return self._sub_getMinNeededTransitions(par, transitions, collisions_per_peptide)

    def _sub_getMinNeededTransitions(self, par, transitions, collisions_per_peptide):
        #take the top j transitions and see whether they, as a tuple, are
        #shared
        min_needed = -1
        for j in range(par.max_uis,0,-1): 
            #take top j transitions
            mytransitions = tuple(sorted([t[1] for t in transitions[:j]]))
            unuseable = False
            for k,v in collisions_per_peptide.iteritems():
                if tuple(sorted(v)[:j]) == mytransitions: unuseable=True
            if not unuseable: min_needed = j
        return min_needed

    # returns the peptide ids and transitions for a peptide from a SRMAltas
    def _get_unique_pepids_toptransitions(self, par, cursor):
        #TODO we select all peptides that are in the peplink table
        #regardless whether their charge is actually correct
        query = """
        select parent_id, q1, q1_charge, ssrcalc, peptide.id, m.sequence
         from %s  srmPep
         inner join ddb.peptide on peptide.id = srmPep.peptide_key
         inner join ddb.peptideOrganism on peptide.id = peptideOrganism.peptide_key 
         inner join hroest.MRMPepLink_final l on l.peptide_key = peptide.id
         inner join hroest.MRMAtlas_qtrap_final_no_pyroGlu m on m.id = l.mrm_key
         where genome_occurence = 1
         and l.charge = q1_charge
         #make sure that the modifications are the same!
         and modified_sequence = left(m.sequence, length(m.sequence) -2)
         %s
         group by parent_id
        """ % (par.peptide_table, par.query_add )
        if par.print_query: print query
        cursor.execute( query )
        res = cursor.fetchall()
        return [
            {
                'parent_id' :  r[0],
                'q1' :         r[1],
                'q1_charge' :  r[2],
                'ssrcalc' :    r[3],
                'peptide_key' :r[4],
                'mod_sequence' :r[5].split('/')[0],
            }
            for r in res
        ]

    def _get_all_transitions_toptransitions(self, par, pep, cursor, values = 'q3, m.id'):
        q3_low, q3_high = par.get_q3range_transitions()
        query1 = """
        select %(values)s
        from %(pep)s p 
        inner join hroest.MRMPepLink_final l on p.peptide_key = l.peptide_key
        inner join hroest.MRMAtlas_qtrap_final_no_pyroGlu m on m.id = l.mrm_key
        where m.parent_charge = p.q1_charge
        and m.sequence = '%(mod_seq)s'
        and p.peptide_key = %(peptide_key)s
        and q3 > %(q3_low)s and q3 < %(q3_high)s         
        and m.parent_charge = %(q1_charge)s
        #make sure that the modifications are the same!
        and modified_sequence = left(m.sequence, length(m.sequence) -2)
        %(query_add)s
        """ % { 'peptide_key' : pep['peptide_key'], 'q3_low' : q3_low,
               'q3_high' : q3_high, 'query_add' : par.query1_add,
               'pep' : par.peptide_table, 'trans' : par.transition_table, 
               'values' : values, 'q1_charge' : pep['q1_charge'], 
               'mod_seq' : pep['mod_sequence'] + '/' + str(pep['q1_charge'])}
        if par.print_query: print query1
        cursor.execute( query1 )
        return cursor.fetchall()

def get_coll_per_peptide_from_precursors(self, transitions, precursors, par, pep, 
        forceNonCpp=False):
    q3_low, q3_high = par.get_q3range_transitions()
    try: 
        #try to use C++ libraries
        if forceNonCpp: import somedummymodulethatwillneverexist
        import c_getnonuis
        return c_getnonuis.calculate_collisions_per_peptide_other_ion_series(
            transitions, precursors, q3_low, q3_high, par.q3_window, par.ppm, par)
    except ImportError:
        # if we dont have any C++ code compiled, calculate fragments 
        R = Residues.Residues('mono')
        RN15 = Residues.Residues('mono')
        RN15.recalculate_monisotopic_data_for_N15()
        collisions = self._get_all_collisions_calculate_sub(precursors,
            par, R, q3_low, q3_high, RN15)

    collisions = list(collisions)
    collisions_per_peptide = {}
    q3_window_used = par.q3_window
    for t in transitions:
        if par.ppm: q3_window_used = par.q3_window * 10**(-6) * t[0]
        for c in collisions:
            if abs( t[0] - c[0] ) <= q3_window_used:
                #gets all collisions
                if collisions_per_peptide.has_key(c[3]):
                    if not t[1] in collisions_per_peptide[c[3]]:
                        collisions_per_peptide[c[3]].append( t[1] )
                else: collisions_per_peptide[c[3]] = [ t[1] ] 
    return collisions_per_peptide 

def get_coll_per_peptide(self, transitions, par, pep, cursor,
        do_not_calculate=False, forceNonCpp=False):
    if do_not_calculate:
        assert False # not supported any more
    else:
        try: 
            #try to use C++ libraries, really fast 50ms or less
            if forceNonCpp: import somedummymodulethatwillneverexist
            return _get_coll_per_peptide_sub(self, transitions, par, pep, cursor)
        except ImportError:
            # second-fastest = 522 
            # if we dont have any C++ code compiled, calculate fragments 
            collisions = list(self._get_all_collisions_calculate_new(
                par, pep, cursor))
    collisions_per_peptide = {}
    q3_window_used = par.q3_window
    for t in transitions:
        if par.ppm: q3_window_used = par.q3_window * 10**(-6) * t[0]
        for c in collisions:
            if abs( t[0] - c[0] ) <= q3_window_used:
                #gets all collisions
                if collisions_per_peptide.has_key(c[3]):
                    if not t[1] in collisions_per_peptide[c[3]]:
                        collisions_per_peptide[c[3]].append( t[1] )
                else: collisions_per_peptide[c[3]] = [ t[1] ] 
    return collisions_per_peptide 

def _get_coll_per_peptide_sub(self, transitions, par, pep, cursor):

    try:
        #use range tree, really fast = 50
        #needs self.c_rangetree and self.parentid_lookup
        import c_getnonuis
        q3_low, q3_high = par.get_q3range_collisions()
        q1 = pep['q1']
        ssrcalc = pep['q1']
        q1_low = q1 - par.q1_window
        q1_high = q1 + par.q1_window
        ssrcalc_low = ssrcalc - par.ssrcalc_window
        ssrcalc_high = ssrcalc + par.ssrcalc_window
        #
        precursor_ids = tuple(self.c_rangetree.query_tree( 
            q1_low, -9999, q1_high,  9999 )  )
        precursors = tuple([self.parentid_lookup[myid[0]] for myid in precursor_ids
                            #dont select myself 
                           if parentid_lookup[myid[0]][2]  != pep['peptide_key']])
        assert par.do_b_y_only() #doesnt for ion series other than b/y 
        return c_getnonuis.calculate_collisions_per_peptide( 
            transitions, precursors, q3_low, q3_high, par.q3_window, par.ppm)
    except AttributeError, ImportError:
        transitions = tuple([ (t[0], i) for i,t in enumerate(transitions)])
        # fast = 100 
        import c_getnonuis
        precursors = self._get_all_precursors(par, pep, cursor)
        if par.do_b_y_only():
            # we gain around 60 % performance when using the optimized function
            return c_getnonuis.calculate_collisions_per_peptide( 
                transitions, precursors, q3_low, q3_high, par.q3_window, par.ppm)
        else: 
            return c_getnonuis.calculate_collisions_per_peptide_other_ion_series( 
            transitions, precursors, q3_low, q3_high, par.q3_window, par.ppm, par)

# Calculate the transitions of a peptide with a given charge (using c++ if possible)
def calculate_transitions_ch(peptides, charges, q3_low, q3_high):
    try: 
        import c_getnonuis
        return c_getnonuis.calculate_transitions_ch(
            peptides, charges, q3_low, q3_high)
    except ImportError:
        return list(_calculate_transitions_ch(
            peptides, charges, q3_low, q3_high))

def _calculate_transitions_ch(peptides, charges, q3_low, q3_high):
    import DDB 
    R = Residues.Residues('mono')
    for p in peptides:
        q1 = p[0]
        peptide_key = p[2]
        peptide = DDB.Peptide()
        peptide.set_sequence(p[1])
        peptide.charge = 2 #dummy, wont need it later
        peptide.create_fragmentation_pattern(R)
        b_series = peptide.b_series
        y_series = peptide.y_series
        for ch in charges:
            for pred in y_series:
                q3 = ( pred + (ch -1)*R.mass_H)/ch
                if q3 < q3_low or q3 > q3_high: continue
                yield (q3, q1, 0, peptide_key)
            for pred in b_series:
                q3 = ( pred + (ch -1)*R.mass_H)/ch
                if q3 < q3_low or q3 > q3_high: continue
                yield (q3, q1, 0, peptide_key)


###UIS Code
from uis_functions import *
from uis_functions import _combinationsDiffLen

# Input: a list of ssrcalcvalues in the for each transition one row (one array)
#           N = [len(v) for v in ssrcalcvalues]
#           strike3_ssrcalcwindow = window of ssrcalc
#
# Output a dictionary whose keys are all the "forbidden" tuples, e.g. tuples of
# transitions that are interfering and can thus not be used for an eUIS.
def thisthirdstrike(N, ssrcalcvalues, strike3_ssrcalcwindow, verbose=False):
    if verbose: print "Started Python function thisthirdstrike"
    M = len(ssrcalcvalues)
    index = [0 for i in range(M)]
    myssr = [0 for i in range(M)]
    discarded_indices = []
    all_nonuis = {}
    # check whether there are any empty ssrcalcvalues
    for k in range(M):
        if len(ssrcalcvalues[k]) == 0:
            discarded_indices.append(k)
            if verbose: print "Python discard index " , k
    if len(discarded_indices) == M: return {}

    # in each iteration we we either advance one or add one to discarded
    # thus we do this at most sum(N) + len(N) times which is bounded by
    # c*k + c
    while True:
        myssr = [-1 for i in range(M)]
        for k in range(M):
            if k in discarded_indices: continue
            myssr[k] = ssrcalcvalues[k][ index[k] ]

        # find the pivot element (the smallest element that is not yet in a discarded group)
        tmin = max(myssr); piv_i = -1
        for k in range(M):
            if k in discarded_indices: continue
            if myssr[k] <= tmin:
                tmin=myssr[k]
                piv_i = k

        # we need to sort by we also need to have a map back to retrieve the original!
        # sorting is O(c log(c) )
        myssr_unsorted = myssr[ : ]
        with_in = [ (a,b) for a,b in enumerate(myssr) ]
        with_in.sort( lambda x,y: cmp(x[1],y[1]))
        sort_idx = [x[0] for x in with_in]
        myssr.sort()
        #if index == [0, 0, 1, 0, 1, 19]: print index, piv_i, tmin, "== ", myssr, sort_idx

        # now find all N different combinations that are not UIS. Since they are
        # sorted we only need to consider elements that have a higher index.
        # all against all is O( c^2 )
        for k in range(M):
          # or myssr[k] == -1 would also work here
          if sort_idx[k] in discarded_indices: continue 
          nonuis = [k]
          for m in range(k+1,M):
              if not sort_idx[m] in discarded_indices and not m == k and not (abs(myssr[k] - myssr[m]) > strike3_ssrcalcwindow):
                  nonuis.append(m)
          backsorted = [sort_idx[n] for n in nonuis]
          backsorted.sort()
          if not tuple(backsorted) in all_nonuis and verbose: 
              print k, "added tuple ", tuple(backsorted), " myssr ", myssr_unsorted #, "index ", index
          all_nonuis[ tuple(backsorted) ] = 0
                    
        # Advance the pivot element
        index[piv_i] += 1
        if(index[piv_i] >= len(ssrcalcvalues[piv_i])):
            discarded_indices.append(piv_i)
            if verbose: print "wanted to advance", piv_i, "had to append to discarded ", discarded_indices
            if len(discarded_indices) == len(ssrcalcvalues): 
                # break out of loop
                break
    return all_nonuis


