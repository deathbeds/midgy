a collection of doit tasks for project specific actions    
    
    def task_format():
run formatters on the code
        
        return dict(actions=["hatch run format:code"])

    def task_docs():
build the docs

        return dict(actions=["hatch run docs:build"], clean=["rm -rf site"])

    def task_test():
test midgy

        return dict(actions=["hatch run test:cov"])


    def task_build():
build the wheel and binaries

        return dict(
            actions=["hatch build"],
            clean=["rm -rf dist"]
        )

    def task_test_release():
a test release to pypi

        return dict(actions=[
            "rm -rf dist",
            "hatch build", 
            "hatch publish -r repo"
        ])

    def task_release():
a release to pypi

        return dict(actions=[
            "rm -rf dist",
            "hatch build", 
            "hatch publish"
        ])

    if __name__ == "__main__":
        import doit, sys
        doit.doit_cmd.DoitMain(doit.cmd_base.ModuleTaskLoader(globals())).run(sys.argv[1:])