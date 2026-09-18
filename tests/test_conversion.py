import importlib.util, pathlib, subprocess, tempfile, hashlib, struct, json
ROOT=pathlib.Path(__file__).parent
spec=importlib.util.spec_from_file_location('converter', ROOT.parent/'src/audio_convert.py')
c=importlib.util.module_from_spec(spec); spec.loader.exec_module(c)
temporary=tempfile.TemporaryDirectory(prefix='finder-audio-test-')
t=pathlib.Path(temporary.name)
ff=c.FFMPEG

def gen(name, rate=48000, codec='pcm_s24le', channels=2):
    path=t/name
    expr='0.1*sin(2*PI*440*t)|0.1*sin(2*PI*880*t)' if channels==2 else ('0.1*sin(2*PI*440*t)' if channels==1 else '|'.join(['0.1*sin(2*PI*440*t)']*channels))
    subprocess.run([ff,'-v','error','-f','lavfi','-i',f'aevalsrc={expr}:s={rate}:d=0.5','-c:a',codec,str(path)],check=True)
    return path

a=gen('한글 space \' $() `quote`.wav')
before=hashlib.sha256(a.read_bytes()).hexdigest()
r=c.convert(a,'mono',{}); assert r['channels']==1 and r['bits']==24 and r['sample_rate']==48000
out=pathlib.Path(r['output'])
def decode(path, channels):
    b=subprocess.check_output([ff,'-v','error','-i',str(path),'-f','f64le','-c:a','pcm_f64le','-'])
    return struct.unpack('<'+'d'*(len(b)//8),b)
x=decode(a,2); y=decode(out,1)
assert max(abs(y[i]-(x[2*i]+x[2*i+1])/2) for i in range(len(y))) < 2e-7
assert c.convert(out,'mono',{})['status']=='skipped'
r2=c.convert(a,'mono',{}); assert r2['output']!=r['output'] and pathlib.Path(r['output']).exists()
r=c.convert(a,'mp3',{}); s,_=c.probe(r['output']); assert s['bit_rate']=='256000' and s['channels']==2 and s['sample_rate']=='48000'
mono=gen('mono.wav',44100,channels=1); r=c.convert(mono,'mp3',{}); assert r['channels']==1 and r['sample_rate']==44100
for name,rate,channels in [('96k.wav',96000,2),('22k.wav',22050,2),('surround.wav',48000,6)]:
    source=gen(name,rate,channels=channels)
    try: c.convert(source,'mp3',{})
    except ValueError: pass
    else: raise AssertionError('Unsupported MP3 input was silently converted')
for fmt,depth in [('wav','16'),('wav','float32'),('aiff','24'),('aiff','float32'),('flac','24'),('alac','24'),('aac','keep'),('mp3','keep')]:
    r=c.convert(a,'custom',{'format':fmt,'rate':44100,'channels':'mono','depth':depth,'bitrate':256})
    assert r['sample_rate']==44100 and r['channels']==1
    if fmt in ('flac','alac','aac','mp3'):
        stereo=c.convert(a,'custom',{'format':fmt,'rate':48000,'channels':'keep','depth':depth,'bitrate':256})
        down=c.convert(stereo['output'],'mono',{}); assert down['channels']==1
for channel,idx in [('left',0),('right',1)]:
    r=c.convert(a,'custom',{'format':'wav','channels':channel,'depth':'keep'})
    z=decode(r['output'],1); assert max(abs(z[i]-x[2*i+idx]) for i in range(len(z)))<2e-7
assert hashlib.sha256(a.read_bytes()).hexdigest()==before
assert not list(t.rglob('.converting-*'))
print('PASS: waveform downmix, formats, bit depth, sample rate, MP3 bitrate, rejection, collisions, source integrity and cleanup')
temporary.cleanup()
