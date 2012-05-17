import unittest
from buildbot.changes.changes import Change
from collective.buildbot.scheduler import SVNScheduler
from collective.buildbot.project import convert_cron_to_setting


class TestScheduler(unittest.TestCase):

    def test_scheduler_does_not_modify_change_object(self):
        """
        SVNScheduler must not change the branch of the incoming change,
        as that one is being used in the next scheduler again
        """
        c = Change('nobody', ['/dev/null'], "no comment",
                   branch = "collective.buildbot/trunk")
        sched = SVNScheduler("test", ['ignores'], \
                             'https....collective.buildbot/trunk')
        sched.addChange(c)
        self.assertTrue(c.branch)

    def test_cron_settings(self):
        """Test parsing of the cron scheduler.
        """
        # All integers
        self.assertEqual(
            [1, 2, 3, 4, 5],
            convert_cron_to_setting('1 2 3 4 5'))
        # Every minute
        self.assertEqual(
            ['*', '*', '*', '*', '*'],
            convert_cron_to_setting('* * * * *'))
        # Minute range
        self.assertEqual(
            [[0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55], 0, 0, '*', '*'],
            convert_cron_to_setting('*/5 0 0 * *'))
        # Hour range
        self.assertEqual(
            [0, [0, 4, 8, 12, 16, 20], '*', '*', '*'],
            convert_cron_to_setting('0 */4 * * *'))
        # Day range
        self.assertEqual(
            [0, 0, [1, 8, 15, 22, 29], '*', '*'],
            convert_cron_to_setting('0 0 */7 * *'))
        # Month range
        self.assertEqual(
            [0, 0, 0, [1, 3, 5, 7, 9, 11], '*'],
            convert_cron_to_setting('0 0 0 */2 *'))
        # Day of week range
        self.assertEqual(
            [0, 0, '*', '*', [0, 2, 4, 6]],
            convert_cron_to_setting('0 0 * * */2'))
        # Hour list
        self.assertEqual(
            [0, [6, 8, 12, 16], '*', '*', '*'],
            convert_cron_to_setting('0 6,8,12,16 * * *'))

    def test_invalid_cron_settings(self):
        """Cron scheduler parser can fail.
        """
        self.assertRaises(
            ValueError, convert_cron_to_setting, 'Whenever I whish')
        self.assertRaises(
            ValueError, convert_cron_to_setting, 'a b c d e')


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestScheduler))
    return suite
