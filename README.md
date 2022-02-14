# Function Dependency Tracer

- Features
  - Generating call graph in static way.
  - Can search specific function or module.
  - Support for Py2 and Py3.

- What it solved?  
It traces dependencies between functions over whole project, even where functions be called can be traced. There are many tools can trace dependencies between modules. However, tools for functions are rare. Here comes the solution, enjoy it!

- How it solved?  
Since Python codes will be transferred to ast(abstract syntax tree) before it becomes binary. With ast nodes(anything in python file are ast nodes. e.g. import ,class, function, attribute), we do the following:  
  1. Collect all function calls.
  2. Search where target function is used. Meanwhile, check if module of target function is imported to avoid name duplicate.
  3. Search where "function used target function" is used recursively until no function is found.

  **NOTE:** This tool can only trace approximately dependencies. It do not handle any kind of ast nodes. Some rare usages might not be traced(--verbose to get details). Still, it can trace most of the cases.

## Installation

```bash
git clone "https://github.com/junyiacademy/func-deps-tracer.git"
```

## Usage

- To trace where a function is used

  ```
  python <path to this tool> <path to your project/file> --function <function name be traced>
  ```

  - Example

    ```
    python trace_function_dependency/trace_function_dependency.py my_project --function foo
    ```

- To trace where functions in a module are used

  ```
  python <path to this tool> <path to your project/file> --module <module name be traced>
  ```

  - Example w/ skip dirs and output as json

    ```
    python trace_function_dependency/trace_function_dependency.py my_project --module foo.py --skip dir1 dir2 --json
    ```

## Output

- Format

  ```
  root, target:
      filepath:lineno, class::function::function
          filepath:lineno, class::function::function::call
              filepath:lineno, function::call
                  filepath:lineno, function::function::call
                  filepath:lineno, function::function::call
      filepath:lineno, function::function::call
          filepath:lineno, function::call
          filepath:lineno, function::call
  ```

- Example

  To trace file below with this command.

  ```
  python trace_function_dependency/trace_function_dependency.py dog.py --function do_something
  ```

  ```python
  # dog.py
  1  def do_something():
  2      # do something
  3      return None
  4
  5  class Dog(object):
  6      def __init__(self, name):
  7          self.name = name
  8
  9      def get_name_and_do_something(self):
  10         do_something()
  11         return self.name
  12
  13 dog = Dog('foo')
  14 dog_name = dog.get_name_and_do_something()
  ```

  This will be the output.
  ```
  root, do_something
      dog.py:10, Dog::get_name_and_do_something::do_something
          dog.py:14, dog.get_name_and_do_something
  ```

## License
Function Dependency Tracer is released under the [MIT](https://opensource.org/licenses/MIT) license.