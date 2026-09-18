import pathlib, plistlib, uuid, shlex, argparse
parser = argparse.ArgumentParser()
parser.add_argument('--output', type=pathlib.Path, required=True)
parser.add_argument('--runtime', type=pathlib.Path, required=True)
parser.add_argument('--python', required=True)
args = parser.parse_args()
ROOT = args.output
LIVE = args.runtime / 'audio_convert.py'
for mode, name in [('mono','Downmix to Mono'), ('mp3','MP3 256 kbps'), ('custom','Custom Settings…'), ('pad','Pad to Next 5 Seconds')]:
    bundle = ROOT / 'workflows' / (name + '.workflow') / 'Contents'
    (bundle / 'Resources').mkdir(parents=True, exist_ok=True)
    command = 'exec ' + shlex.quote(args.python) + ' ' + shlex.quote(str(LIVE)) + ' ' + mode + ' -- "$@"'
    uid = lambda: str(uuid.uuid4()).upper()
    action = {
        'ActionBundlePath':'/System/Library/Automator/Run Shell Script.action',
        'ActionName':'Run Shell Script', 'ActionParameters':{'COMMAND_STRING':command, 'inputMethod':1, 'shell':'/bin/zsh', 'source':'', 'CheckedForUserDefaultShell':True},
        'AMAccepts':{'Container':'List','Optional':True,'Types':['com.apple.cocoa.string']},
        'AMProvides':{'Container':'List','Types':['com.apple.cocoa.string']},
        'AMActionVersion':'2.0.3', 'AMParameterProperties':{k:{} for k in ['COMMAND_STRING','inputMethod','shell','source','CheckedForUserDefaultShell']},
        'AMRequiredResources':[], 'Application':['Automator'], 'BundleIdentifier':'com.apple.RunShellScript',
        'CanShowSelectedItemsWhenRun':False, 'CanShowWhenRun':False, 'Category':['AMCategoryUtilities'],
        'CFBundleVersion':'2.0.3', 'Class Name':'RunShellScriptAction', 'InputUUID':uid(), 'OutputUUID':uid(), 'UUID':uid(),
        'ShowWhenRun':False, 'isViewVisible':True,
    }
    data = {'AMApplicationBuild':'523','AMApplicationVersion':'2.10','AMDocumentVersion':'2',
            'actions':[{'action':action,'isViewVisible':True}], 'connectors':{},
            'workflowMetaData':{'serviceApplicationBundleID':'com.apple.finder',
                'serviceApplicationPath':'/System/Library/CoreServices/Finder.app',
                'serviceInputTypeIdentifier':'com.apple.Automator.fileSystemObject.music',
                'serviceOutputTypeIdentifier':'com.apple.Automator.nothing',
                'serviceProcessesInput':0, 'workflowTypeIdentifier':'com.apple.Automator.servicesMenu',
                'useAutomaticInputType':False, 'presentationMode':15}}
    info = {'CFBundleIdentifier':'io.github.nearfield.finder-audio.'+mode, 'CFBundleName':name,
            'CFBundleShortVersionString':'1.1.0','CFBundleVersion':'3','CFBundleDevelopmentRegion':'en','CFBundleIconFile':'AudioConverter.icns',
            'NSServices':[{'NSIconName':'NSTouchBarAudioOutputVolumeHigh', 'NSBackgroundColorName':'background', 'NSMenuItem':{'default':name}, 'NSMessage':'runWorkflowAsService',
                 'NSRequiredContext':{'NSApplicationIdentifier':'com.apple.finder'},
                 'NSSendFileTypes':['public.audio']}]}
    (bundle/'Resources/AudioConverter.icns').write_bytes((ROOT/'Finder Audio Converter.app/Contents/Resources/AudioConverter.icns').read_bytes())
    (bundle/'Info.plist').write_bytes(plistlib.dumps(info))
    (bundle/'Resources/document.wflow').write_bytes(plistlib.dumps(data))
print('Built 4 workflows')
