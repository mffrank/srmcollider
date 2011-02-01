import unittest
import test_rangetree, test_cgetnonuis, test_collider, test_db

verbosity = 2

cgetnonuis_suite = unittest.TestLoader().loadTestsFromTestCase(test_cgetnonuis.Test_cgetnonuis)
crangetree_suite = unittest.TestLoader().loadTestsFromTestCase(test_rangetree.Test_crangetree)
collider_sqlite_suite = unittest.TestLoader().loadTestsFromTestCase(test_db.Test_collider_sqlite)
collider_function_suite = unittest.TestLoader().loadTestsFromTestCase(test_collider.Test_collider_function)

unittest.TextTestRunner(verbosity=1).run(cgetnonuis_suite)
unittest.TextTestRunner(verbosity=1).run(crangetree_suite)
unittest.TextTestRunner(verbosity=1).run(collider_function_suite)
#unittest.TextTestRunner(verbosity=2).run(collider_sqlite_suite)



