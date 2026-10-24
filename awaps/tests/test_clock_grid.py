import ast
import importlib.util
import json
import pathlib
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from indi_allsky.clock_grid import ClockGrid,load_clock_grid

class Clock:
    def __init__(self, wall=0):
        self.wall=float(wall);self.mono=0.;self.jump=None
    def time(self):return self.wall
    def monotonic(self):return self.mono
    def sleep(self, seconds):
        self.wall+=seconds;self.mono+=seconds
        if self.jump is not None:
            self.wall+=self.jump;self.jump=None

class GridTests(unittest.TestCase):
    def test_startup_waits_for_next_fixed_slot(self):
        for now,target in [(0,10),(10,25),(11,25),(59,70)]:
            c=Clock(now);g=ClockGrid(clock=c)
            self.assertEqual(g.wait(15),target)
    def test_hundreds_of_late_cycles_do_not_accumulate_drift(self):
        c=Clock();g=ClockGrid(clock=c)
        first=g.wait(15)
        for i in range(1,500):
            c.wall=first+i*15+.05;c.mono+=15
            self.assertEqual(g.wait(15),first+i*15)
        self.assertEqual(g.skipped,0)
    def test_missing_a_slot_waits_for_the_next_one(self):
        c=Clock();g=ClockGrid(clock=c);g.wait(15)
        c.wall=25.101
        self.assertEqual(g.wait(15),40)
        self.assertEqual(g.skipped,1)
    def test_busy_for_multiple_cycles_does_not_burst(self):
        c=Clock();g=ClockGrid(clock=c);g.wait(15);c.wall=70.05
        self.assertEqual(g.wait(15),70)
        self.assertEqual(g.skipped,3)
        self.assertEqual(g.wait(15),85)
    def test_period_change_uses_shared_phase(self):
        c=Clock();g=ClockGrid(clock=c);g.wait(15)
        self.assertEqual(g.wait(30),40)
        self.assertEqual(g.wait(45),55)
    def test_queue_backoff_only_skips_grid_slots(self):
        c=Clock();g=ClockGrid(clock=c);g.wait(15);c.wall=29
        self.assertEqual(g.wait(15),40)
    def test_forward_clock_step_recomputes_target(self):
        c=Clock();g=ClockGrid(clock=c);c.jump=100
        target=g.wait(15)
        self.assertEqual((target-10)%15,0);self.assertGreater(target,100)
    def test_backward_clock_step_never_duplicates_a_slot(self):
        c=Clock();g=ClockGrid(clock=c);g.wait(15);c.jump=-60
        self.assertEqual(g.wait(15),25)
    def test_15_30_and_45_second_grids_share_the_phase(self):
        for period in (15,30,45):
            c=Clock(1);g=ClockGrid(clock=c)
            for _ in range(4):self.assertAlmostEqual((g.wait(period)-10)%period,0)
    def test_invalid_period_or_lateness_fails_closed(self):
        for p in (0,14,301,float('nan')):
            with self.assertRaises(ValueError):ClockGrid(clock=Clock()).wait(p)
        for late in (0,-1,.101,float('nan')):
            with self.assertRaises(ValueError):ClockGrid(max_lateness=late)
    def test_opt_in_settings(self):
        with tempfile.TemporaryDirectory() as temp:
            p=pathlib.Path(temp)/'grid.json'
            self.assertIsNone(load_clock_grid(p))
            p.write_text('{"enabled":false}');self.assertIsNone(load_clock_grid(p))
            p.write_text('{"enabled":true}');self.assertIsInstance(load_clock_grid(p),ClockGrid)
            p.write_text('{"enabled":"false"}')
            with self.assertRaises(ValueError):load_clock_grid(p)

# Compile the actual driver method, replacing only hardware bindings. This
# checks where the gate runs relative to device setup and sendNewNumber.
class DriverTests(unittest.TestCase):
    def method(self):
        source=ast.parse((ROOT/'indi_allsky/camera/indi.py').read_text())
        cls=next(n for n in source.body if isinstance(n,ast.ClassDef) and n.name=='IndiClient')
        method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='set_number')
        cls=ast.ClassDef(name='Driver',bases=[],keywords=[],body=[method],decorator_list=[])
        tree=ast.fix_missing_locations(ast.Module(body=[cls],type_ignores=[]))
        import logging
        scope={'logger':logging.getLogger('test'),'time':types.SimpleNamespace(time=lambda:self.clock.wall),
               'constants':types.SimpleNamespace(NIGHT_NIGHT=0),'PyIndi':types.SimpleNamespace(IP_RO=0)}
        exec(compile(tree,'actual-set_number','exec'),scope)
        return scope['Driver']
    def driver(self, enabled=True):
        self.clock=Clock();events=[]
        d=self.method()();d.config={'EXPOSURE_PERIOD':15};d.night_av=[True]
        d._awaps_clock_grid=ClockGrid(clock=self.clock) if enabled else None
        control=types.SimpleNamespace(getPermission=lambda:1,getLabel=lambda:'Exposure',setValue=lambda v:events.append(('value',self.clock.wall)))
        class Controls(list):
            def getPermission(self):return 1
        d.get_control=lambda *args:Controls([control])
        setattr(d,'_Driver__map_indexes',lambda *args:{'CCD_EXPOSURE_VALUE':0})
        d.sendNewNumber=lambda c:events.append(('send',self.clock.wall))
        return d,events
    def test_preparation_before_gate_and_send_on_slot(self):
        d,e=self.driver();d.set_number(None,'CCD_EXPOSURE',{'CCD_EXPOSURE_VALUE':9},sync=False)
        self.assertEqual(e[0],('value',0.));self.assertEqual(e[-1],('send',10.));self.assertEqual(d.exposureStartTime,10)
    def test_disabled_mode_sends_without_waiting(self):
        d,e=self.driver(False);d.set_number(None,'CCD_EXPOSURE',{'CCD_EXPOSURE_VALUE':9},sync=False)
        self.assertEqual(e[-1],('send',0.))
    def test_non_exposure_controls_are_not_gated(self):
        d,e=self.driver();d.set_number(None,'CCD_GAIN',{'CCD_EXPOSURE_VALUE':9},sync=False)
        self.assertEqual(e[-1],('send',0.))
    def test_daytime_is_not_gated(self):
        d,e=self.driver();d.night_av=[False];d.set_number(None,'CCD_EXPOSURE',{'CCD_EXPOSURE_VALUE':9},sync=False)
        self.assertEqual(e[-1],('send',0.))
    def test_unsupported_sqm_mode_refuses_exposure(self):
        d,e=self.driver();d.config['CAMERA_SQM']={'ENABLE':True}
        with self.assertRaises(ValueError):d.set_number(None,'CCD_EXPOSURE',{'CCD_EXPOSURE_VALUE':9},sync=False)
        self.assertFalse(any(k=='send' for k,t in e))

if __name__=='__main__':unittest.main()
