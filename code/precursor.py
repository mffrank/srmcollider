import Residues
import c_getnonuis
R = Residues.Residues('mono')
class Precursor:

  def __init__(self):
      pass

  def initialize(self, modified_sequence, transition_group, parent_id, q1_charge, q1, ssrcalc, modifications, missed_cleavages, isotopically_modified):
    self.modified_sequence      = modified_sequence      
    self.transition_group       = transition_group       
    self.parent_id              = parent_id              
    self.q1_charge              = q1_charge              
    self.q1                     = q1                     
    self.ssrcalc                = ssrcalc                
    self.modifications          = modifications          
    self.missed_cleavages       = missed_cleavages       
    self.isotopically_modified  = isotopically_modified  

  def calculate_transitions(self, q3_low, q3_high, charges=[1]):
    transitions = c_getnonuis.calculate_transitions_ch(
        ((self.q1, self.modified_sequence, self.parent_id),), charges, q3_low, q3_high)
    # fake some srm_id for the transitions, so that the returned transitions will be tuples of (q1, id)
    return tuple([ (t[0], i) for i,t in enumerate(transitions)])

class Precursors:
  """A class that abstracts getting and receiving precursors from the db"""

  def __init__(self):
    self.precursors = []

  def getFromDB(self, par, cursor, min_q1, max_q1):
    # Get all precursors from the DB within a window of Q1
    self.precursors = []
    isotope_correction = par.isotopes_up_to * R.mass_diffC13 / min(par.parent_charges)
    q =  """
    select modified_sequence, transition_group, parent_id, q1_charge, q1, ssrcalc, modifications, missed_cleavages, isotopically_modified
    from %(peptide_table)s where q1 between %(lowq1)s - %(isotope_correction)s and %(highq1)s
    """ % {'peptide_table' : par.peptide_table, 
                  'lowq1'  : min_q1 - par.q1_window, 
                  'highq1' : max_q1 + par.q1_window,
                  'isotope_correction' : isotope_correction
          } 
    cursor.execute(q)
    for res in cursor.fetchall():
      p = Precursor()
      p.initialize(*res)
      self.precursors.append(p)

  def build_parent_id_lookup(self):
    self.parentid_lookup = dict([ [ p.parent_id, p] for p in self.precursors])

  def lookup_by_parent_id(self, parent_id):
    return self.parentid_lookup[parent_id]

  def build_transition_group_lookup(self):
    self.transition_group_lookup = dict([ [ p.transition_group, p] for p in self.precursors])

  def loopup_by_transition_group(self, parent_id):
    return self.transition_group_lookup[transition_group]

  def build_rangetree(self):
    """
    * The tuples have the following structure:
    *   0
    *   1 
    *   2 - parent_id
    *   3 - q1_charge
    *   4 - q1
    *   5 - ssrcalc
    """
    import c_rangetree
    alltuples = [ (0,0, p.parent_id, p.q1_charge, p.q1, p.ssrcalc) for p in self.precursors]
    c_rangetree.create_tree(tuple(alltuples))
    return c_rangetree

  def get_collisions_per_peptide(self, precursor, transitions, par):
    """Get the collisions per peptide, e.g. a dictionary that contains the
    interfered transitions for a given precursor with given transitions.
    """
    import c_rangetree
    q3_low, q3_high = par.get_q3range_transitions()
    q1_low  = precursor.q1 - par.q1_window 
    q1_high = precursor.q1 + par.q1_window
    #correct rounding errors, s.t. we get the same results as before!
    ssrcalc_low  = precursor.ssrcalc - par.ssrcalc_window + 0.001
    ssrcalc_high = precursor.ssrcalc + par.ssrcalc_window - 0.001
    isotope_correction = par.isotopes_up_to * R.mass_diffC13 / min(par.parent_charges)

    # Get the precursor ids of the interfering precursors from the rangetree
    precursor_ids = c_rangetree.query_tree(
        precursor.q1 - par.q1_window,
        ssrcalc_low, 
        precursor.q1 + par.q1_window,
        ssrcalc_high,
        par.isotopes_up_to, isotope_correction)  

    # Now deselect the myself (the precursor passed as argument) and reformat
    globalprecursors = [self.lookup_by_parent_id(myid[0]) for myid in precursor_ids
      #dont select myself 
      if self.lookup_by_parent_id(myid[0]).transition_group != precursor.transition_group]

    # expected precursor tuple parent_id : xxx, sequence, trans_group, xxxx, isotope modification
    globalprecursors = tuple([(0, p.modified_sequence, p.transition_group, 0, p.isotopically_modified) for p in globalprecursors])
    return c_getnonuis.calculate_collisions_per_peptide_other_ion_series( 
        transitions, globalprecursors, q3_low, q3_high, par.q3_window, par.ppm, par)



